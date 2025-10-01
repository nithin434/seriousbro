# Prayana FastAPI Logging Integration

## Overview
The FastAPI application now uses a comprehensive logging system with day-wise log rotation and structured JSON logging.

## Logger Configuration
- **Location**: `logger_config.py`
- **Log Directory**: `logs/` (created automatically)
- **Log Rotation**: 10MB per file, keeps 30 backup files
- **Format**: JSON structured logs with timestamps

## Log Types

### 1. API Request Logs (`logs/api_requests.log`)
Automatically logs all incoming API requests with:
- Method, endpoint, user ID
- Response status code and duration
- Query parameters and client IP
- Timestamp in ISO format

### 2. Authentication Logs (`logs/authentication.log`)
Tracks authentication events:
- Login attempts and results
- Password verification
- Token validation
- User signup activities

### 3. Booking Activity Logs (`logs/bookings.log`)
Monitors booking and ride operations:
- Booking creation attempts and results
- Ride start/end events
- Bike status changes
- Stall deposits and transfers

### 4. Error Logs (`logs/errors.log`)
Captures all application errors:
- Exception details with stack traces
- User context and endpoint information
- Error classification and severity

### 5. System Logs (`logs/system.log`)
Records system-level events:
- Application startup/shutdown
- Configuration changes
- System health events

## Implementation Details

### Middleware Integration
```python
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Automatically logs all API requests with timing
```

### Authentication Logging
```python
# Login attempts
prayana_logger.log_authentication("LOGIN_ATTEMPT", email=user_email)

# Successful login
prayana_logger.log_authentication("LOGIN_SUCCESS", email=user_email, user_id=user_id)

# Failed login
prayana_logger.log_authentication("LOGIN_FAILED", email=user_email, success=False, reason="Invalid password")
```

### Booking Activity Logging
```python
# Booking creation
prayana_logger.log_booking_activity("BOOKING_CREATE_SUCCESS", booking_id=booking_id, user_id=user_id, bike_id=bike_id)

# Ride completion
prayana_logger.log_booking_activity("END_RIDE_SUCCESS", booking_id=booking_id, user_id=user_id, details={...})
```

### Error Logging
```python
# Exception handling
prayana_logger.log_error("BOOKING_CREATE_ERROR", str(e), user_id=user_id, endpoint="/api/bookings/create", stack_trace=traceback.format_exc())
```

## Log File Structure

### Example API Request Log Entry:
```json
{
  "type": "API_REQUEST",
  "method": "POST",
  "endpoint": "/api/bookings/create",
  "user_id": "Prayana20250928201234ABCD",
  "status_code": 200,
  "duration_ms": 125.45,
  "timestamp": "2025-09-30T14:30:25.123456",
  "query_params": {},
  "client_ip": "35.200.140.65"
}
```

### Example Authentication Log Entry:
```json
{
  "type": "AUTH_EVENT",
  "action": "LOGIN_SUCCESS",
  "email": "admin@prayana.com",
  "user_id": "Prayana20250928201234ABCD",
  "success": true,
  "reason": null,
  "timestamp": "2025-09-30T14:30:25.123456"
}
```

### Example Booking Activity Log Entry:
```json
{
  "type": "BOOKING_ACTIVITY",
  "action": "END_RIDE_SUCCESS",
  "booking_id": "BK202509282014249BA0",
  "user_id": "Prayana20250928201234ABCD",
  "bike_id": "Prayana7307",
  "details": {
    "ride_id": "RD202509282014567B2C",
    "duration_minutes": 45,
    "final_fare": 150.0,
    "destination_stall_id": "STALL2025092612155912A0",
    "destination_stall_name": "VIT Main Gate"
  },
  "timestamp": "2025-09-30T14:30:25.123456"
}
```

### Example Error Log Entry:
```json
{
  "type": "ERROR",
  "error_type": "BOOKING_CREATE_ERROR",
  "message": "Bike not available",
  "user_id": "Prayana20250928201234ABCD",
  "endpoint": "/api/bookings/create",
  "stack_trace": "Traceback (most recent call last):\n...",
  "timestamp": "2025-09-30T14:30:25.123456"
}
```

## Benefits

### 1. **Day-wise Log Rotation**
- Logs automatically rotate when they reach 10MB
- 30 backup files are maintained for historical data
- Easy to find logs for specific dates

### 2. **Structured JSON Format**
- Machine-readable format for log analysis
- Consistent structure across all log types
- Easy integration with log analysis tools

### 3. **Comprehensive Coverage**
- All API requests automatically logged
- User actions tracked with context
- Errors captured with full debugging information

### 4. **Performance Monitoring**
- Request duration tracking
- Response status monitoring
- System performance insights

### 5. **Security Auditing**
- Authentication attempt tracking
- User activity monitoring
- Failed access attempt detection

## Log Analysis

### View Recent API Requests:
```bash
tail -f logs/api_requests.log | jq '.'
```

### Find Failed Login Attempts:
```bash
grep "LOGIN_FAILED" logs/authentication.log | jq '.'
```

### Monitor Booking Activities:
```bash
tail -f logs/bookings.log | jq 'select(.action | contains("BOOKING"))'
```

### Check Recent Errors:
```bash
tail -n 50 logs/errors.log | jq '.'
```

## Integration Status

✅ **Completed Integrations:**
- API request middleware logging
- Authentication event logging
- Booking activity tracking
- Error handling with detailed logging
- System startup logging

✅ **Log Categories Implemented:**
- API requests with timing
- Authentication events
- Booking and ride operations
- Application errors
- System events

✅ **Features:**
- JSON structured format
- Automatic log rotation
- User context tracking
- Performance metrics
- Error stack traces

The logging system is now fully integrated and will capture comprehensive application activity in organized, day-wise log files.