from app.models.counter import Counter


async def get_next_student_id_offline():
    """
    Get the next student UID and student_id from local counter when offline.
    
    Returns:
        dict: Dictionary containing uid and student_id
    """
    try:
        # Look for our main student counter
        counter = await Counter.find_one(Counter.name == "student_sequence")
        
        if not counter:
            # Initialize counter starting from 10019 (next after your last UID 10018)
            counter = Counter(name="student_sequence", value=10019)
            await counter.insert()
        else:
            # Increment the counter
            counter.value += 1
            await counter.save()
        
        # Use the same value for both UID and student_id
        next_id = counter.value
        
        return {
            "uid": next_id,
            "student_id": str(next_id)  # Convert to string for student_id
        }
        
    except Exception as e:
        # Fallback: if counter fails, start from a safe number
        import time
        fallback_id = int(time.time()) % 100000 + 20000  # Start from 20000+ range
        return {
            "uid": fallback_id,
            "student_id": str(fallback_id)
        }


async def peek_next_student_id_offline():
    """
    Get the next student UID and student_id from local counter WITHOUT incrementing.
    This is used when we want to reserve IDs but only increment after successful creation.
    
    Returns:
        dict: Dictionary containing uid and student_id
    """
    try:
        # Look for our main student counter
        counter = await Counter.find_one(Counter.name == "student_sequence")
        
        if not counter:
            # Initialize counter starting from 10019 (next after your last UID 10018)
            counter = Counter(name="student_sequence", value=10018)  # Start from 10018, so next is 10019
            await counter.insert()
        
        # Get next ID without incrementing
        next_id = counter.value + 1
        
        return {
            "uid": next_id,
            "student_id": str(next_id)  # Convert to string for student_id
        }
        
    except Exception as e:
        # Fallback: if counter fails, start from a safe number
        import time
        fallback_id = int(time.time()) % 100000 + 20000  # Start from 20000+ range
        return {
            "uid": fallback_id,
            "student_id": str(fallback_id)
        }


async def increment_student_counter():
    """
    Increment the student counter after successful student creation.
    This should be called only after the student has been successfully created.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        counter = await Counter.find_one(Counter.name == "student_sequence")
        
        if not counter:
            # Initialize counter starting from 10019
            counter = Counter(name="student_sequence", value=10019)
            await counter.insert()
        else:
            # Increment the counter
            counter.value += 1
            await counter.save()
        
        print(f"✅ Student counter incremented to {counter.value}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to increment student counter: {e}")
        return False


async def sync_local_counter_with_remote(remote_uid: int):
    """
    Update local counter to match the UID received from remote backend.
    This keeps local and remote counters synchronized.
    
    Args:
        remote_uid: The UID received from remote backend
    """
    try:
        counter = await Counter.find_one(Counter.name == "student_sequence")
        
        if not counter:
            # Create counter with the remote UID value
            counter = Counter(name="student_sequence", value=remote_uid)
            await counter.insert()
        else:
            # Update counter to match remote UID
            counter.value = remote_uid
            await counter.save()
            
        print(f"✅ Local counter synced to {remote_uid}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to sync local counter: {e}")
        return False


async def initialize_student_counter(start_value: int = 10018):
    """
    Initialize the student counter to a specific value.
    
    Args:
        start_value: The starting value for the counter (current last UID)
    """
    try:
        counter = await Counter.find_one(Counter.name == "student_sequence")
        
        if not counter:
            counter = Counter(name="student_sequence", value=start_value)
            await counter.insert()
        else:
            counter.value = start_value
            await counter.save()
            
        print(f"✅ Student counter initialized to {start_value}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to initialize student counter: {e}")
        return False
