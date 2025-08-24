import socketio
from typing import Dict, Any

# Global Socket.IO server instance
sio = None

def init_socketio(socketio_server: socketio.AsyncServer):
    """Initialize the Socket.IO server reference"""
    global sio
    sio = socketio_server
    
    # Register event handlers
    register_event_handlers()
    
    print("✅ Socket.IO manager initialized")

async def broadcast_attendance(attendance_data: Dict[str, Any]):
    """Broadcast attendance data to all connected Socket.IO clients
    
    Handles both 'attendance_update' and 'decision_request' event types
    """
    global sio
    try:
        if sio:
            # Determine event type based on data
            event_type = attendance_data.get('type', 'attendance_update')
            
            if event_type == 'decision_request':
                # Special handling for decision requests
                await sio.emit('decision_request', attendance_data)
                print(f"📨 Broadcasting decision request to Socket.IO clients: {attendance_data.get('student_name', 'Unknown')} - {attendance_data.get('reason', 'Unknown reason')}")
            else:
                # Regular attendance update
                await sio.emit('attendance_update', attendance_data)
                print(f"📡 Broadcasting attendance to Socket.IO clients: {attendance_data.get('student_name', 'Unknown')} - Status: {attendance_data.get('status', 'unknown')}")
        else:
            print("⚠️ Socket.IO server not initialized, cannot broadcast")
    except Exception as e:
        print(f"⚠️ Error broadcasting via Socket.IO: {e}")

def register_event_handlers():
    """Register Socket.IO event handlers"""
    global sio
    
    if not sio:
        print("⚠️ Cannot register handlers: Socket.IO server not initialized")
        return

    @sio.event
    async def connect(sid, environ, auth):
        """Handle client connection"""
        print(f"🔗 Client connected: {sid}")
        if auth:
            print(f"🔐 Auth data received: {auth}")
        await sio.emit('connection_status', {'status': 'connected', 'message': 'Successfully connected to attendance system'}, room=sid)
    
    @sio.event
    async def disconnect(sid):
        """Handle client disconnection"""
        print(f"🔌 Client disconnected: {sid}")
    
    @sio.event
    async def decision_response(sid, data):
        """Handle decision responses from frontend"""
        try:
            print(f"📨 Decision response received from {sid}: {data}")
            
            decision_id = data.get('decision_id')
            decision = data.get('decision')  # 'approve' or 'reject'
            
            if decision_id and decision:
                # Import here to avoid circular imports
                from app.routes.fingerprint_attendance import process_assistant_decision
                
                # Process the decision
                result = await process_assistant_decision(decision_id, decision)
                
                if result['success']:
                    if decision == 'approve':
                        # Send approval confirmation
                        await sio.emit('decision_response', {
                            'success': True,
                            'decision': decision,
                            'decision_id': decision_id,
                            'message': f'✅ Attendance approved successfully'
                        }, room=sid)
                        
                        # Also broadcast the final attendance update
                        await broadcast_attendance({
                            "type": "attendance_update",
                            "uid": data.get('uid', 'Unknown'),
                            "student_id": data.get('uid', 'Unknown'),
                            "student_name": data.get('student_name', 'Unknown Student'),
                            "status": "approved",
                            "mode": "online",
                            "is_correct_group": True,
                            "message": f"✅ تم الموافقة على حضور {data.get('student_name', 'الطالب')}",
                            "requires_approval": False
                        })
                    else:
                        # Send rejection confirmation  
                        await sio.emit('decision_response', {
                            'success': True,
                            'decision': decision,
                            'decision_id': decision_id,
                            'message': f'❌ Attendance rejected'
                        }, room=sid)
                        
                        # Also broadcast the final attendance update
                        await broadcast_attendance({
                            "type": "attendance_update",
                            "uid": data.get('uid', 'Unknown'),
                            "student_id": data.get('uid', 'Unknown'), 
                            "student_name": data.get('student_name', 'Unknown Student'),
                            "status": "rejected",
                            "mode": "online",
                            "is_correct_group": False,
                            "message": f"❌ تم رفض حضور {data.get('student_name', 'الطالب')}",
                            "requires_approval": False
                        })
                else:
                    # Send error response
                    await sio.emit('decision_response', {
                        'success': False,
                        'error': result.get('error', 'Unknown error'),
                        'decision_id': decision_id
                    }, room=sid)
            else:
                await sio.emit('decision_response', {
                    'success': False,
                    'error': 'Missing decision_id or decision'
                }, room=sid)
                
        except Exception as e:
            print(f"❌ Error processing decision from {sid}: {e}")
            await sio.emit('decision_response', {
                'success': False,
                'error': str(e)
            }, room=sid)
    
    print("✅ Socket.IO event handlers registered")
