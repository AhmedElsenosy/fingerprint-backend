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
        try:
            conn.enroll_user(uid, 0, 0)  # If this raises, try conn.enroll_user(uid, 0)
        except Exception as enroll_err:
            print(f"⚠️ enroll_user with 3 args failed: {enroll_err}. Trying with 2 args...")
            try:
                conn.enroll_user(uid, 0)
            except Exception as fallback_err:
                print(f"❌ Both enrollment attempts failed: {fallback_err}")
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

