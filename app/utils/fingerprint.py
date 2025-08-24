import base64
from zk import ZK
from zk.finger import Finger  # optional, for clarity

def connect_device():
    try:
        zk = ZK('192.168.1.201', port=4370, timeout=5)
        conn = zk.connect()
        return conn
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return None

def enroll_fingerprint(uid: int, name: str):
    conn = connect_device()
    if not conn:
        print("❌ Could not connect to fingerprint device")
        return None

    try:
        print(f"🔍 Starting fingerprint enrollment for UID={uid}, Name={name}")
        conn.disable_device()

        # Delete user if exists
        users = conn.get_users()
        user_exists = any(u.uid == uid for u in users)
        if user_exists:
            print(f"⚠️ User with UID={uid} already exists. Deleting first.")
            conn.delete_user(uid=uid)

        # Set user on the device
        conn.set_user(
            uid=uid,
            name=name,
            privilege=0,
            password='',
            group_id='',
            user_id=str(uid)
        )

        # Enroll user — some devices may expect only uid and finger_id
        enrollment_success = False
        try:
            print(f"🔍 Attempting fingerprint enrollment (3 args) for UID {uid}...")
            conn.enroll_user(uid, 0, 0)  # If this raises, try conn.enroll_user(uid, 0)
            enrollment_success = True
            print(f"✅ Fingerprint enrollment (3 args) successful")
        except Exception as enroll_err:
            error_msg = str(enroll_err).lower()
            if "timed out" in error_msg or "timeout" in error_msg:
                print(f"⚠️ Fingerprint enrollment timed out. This usually means no finger was placed or device is busy.")
            else:
                print(f"⚠️ enroll_user with 3 args failed: {enroll_err}")
            
            try:
                print(f"🔍 Attempting fingerprint enrollment (2 args) for UID {uid}...")
                conn.enroll_user(uid, 0)
                enrollment_success = True
                print(f"✅ Fingerprint enrollment (2 args) successful")
            except Exception as fallback_err:
                fallback_error_msg = str(fallback_err).lower()
                if "timed out" in fallback_error_msg or "timeout" in fallback_error_msg:
                    print(f"❌ Both enrollment attempts timed out. Please ensure finger is placed on scanner and try again.")
                else:
                    print(f"❌ Both enrollment attempts failed: {fallback_err}")
                return None
        
        if not enrollment_success:
            return None

        # Get fingerprint template
        template = conn.get_user_template(uid, 0)
        if not template:
            print("❌ No fingerprint template retrieved")
            return None

        # Debug template structure
        print(f"📌 Template type: {type(template)}")
        print(f"📌 Template dir: {dir(template)}")

        # Extract raw fingerprint data
        if hasattr(template, "template"):
            raw = template.template
        elif hasattr(template, "serialize"):
            raw = template.serialize()
        elif isinstance(template, str):
            raw = template.encode()
        else:
            raise AttributeError("❌ Unsupported fingerprint template format")

        # Encode to base64
        encoded_template = base64.b64encode(raw).decode()
        print("✅ Fingerprint enrolled and encoded successfully")
        return encoded_template

    except Exception as e:
        print(f"❌ Enrollment error: {e}")
        return None

    finally:
        conn.enable_device()
        conn.disconnect()
        print("🔌 Device re-enabled and disconnected")


def identify_user():
    conn = connect_device()
    if not conn:
        print("❌ Cannot connect to fingerprint device")
        return None

    try:
        conn.disable_device()
        print("🖐 Waiting for fingerprint...")

        # Wait for fingerprint match
        user = conn.identify_user()
        if user:
            print(f"✅ Fingerprint matched: UID={user.uid}, Name={user.name}")
            return user  # returns a User object with `uid`, `name`, etc.
        else:
            print("❌ No match found")
            return None

    except Exception as e:
        print(f"❌ Error during fingerprint identification: {e}")
        return None

    finally:
        conn.enable_device()
        conn.disconnect()
        print("🔌 Device re-enabled and disconnected")

