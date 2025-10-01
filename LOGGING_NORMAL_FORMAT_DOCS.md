# Prayana Logging - Normal Text Format

## Overview
The logging system now uses human-readable text format instead of JSON for better readability and easier debugging.

## Log Format Structure
```
YYYY-MM-DD HH:MM:SS | LEVEL | MESSAGE
```

## Sample Log Entries

### 1. API Request Logs (`logs/api_requests.log`)
```
2025-09-30 14:30:25 | INFO | POST /api/bookings/create | User: Prayana20250928201234ABCD | Status: 200 | Duration: 125.45ms | IP: 35.200.140.65 | Params: {}
2025-09-30 14:31:10 | INFO | GET /api/bookings/user | User: Prayana20250928201234ABCD | Status: 200 | Duration: 45.23ms | IP: 35.200.140.65 | Params: {'page': '1', 'limit': '10'}
2025-09-30 14:32:05 | INFO | POST /api/bookings/end/BK202509282014249BA0 | User: Prayana20250928201234ABCD | Status: 200 | Duration: 234.67ms | IP: 35.200.140.65
```

### 2. Authentication Logs (`logs/authentication.log`)
```
2025-09-30 14:25:15 | INFO | AUTH LOGIN_ATTEMPT | Email: admin@prayana.com | Success: True
2025-09-30 14:25:16 | INFO | AUTH PASSWORD_VERIFIED | Email: admin@prayana.com | UserID: Prayana20250928201234ABCD | Success: True
2025-09-30 14:25:17 | INFO | AUTH LOGIN_SUCCESS | Email: admin@prayana.com | UserID: Prayana20250928201234ABCD | Success: True
2025-09-30 14:28:42 | WARNING | AUTH LOGIN_FAILED | Email: user@test.com | Success: False | Reason: Invalid password
```

### 3. Booking Activity Logs (`logs/bookings.log`)
```
2025-09-30 14:30:25 | INFO | BOOKING BOOKING_CREATE_ATTEMPT | UserID: Prayana20250928201234ABCD | BikeID: Prayana7307
2025-09-30 14:30:26 | INFO | BOOKING BOOKING_CREATE_SUCCESS | BookingID: BK202509282014249BA0 | UserID: Prayana20250928201234ABCD | BikeID: Prayana7307 | pickup_stall_id: STALL202509261215592AEB | estimated_price: 400.0 | estimated_duration: 120
2025-09-30 14:45:30 | INFO | BOOKING END_RIDE_ATTEMPT | BookingID: BK202509282014249BA0 | UserID: Prayana20250928201234ABCD | destination_stall_id: STALL2025092612155912A0 | total_active_time: 45
2025-09-30 14:45:32 | INFO | BOOKING END_RIDE_SUCCESS | BookingID: BK202509282014249BA0 | UserID: Prayana20250928201234ABCD | BikeID: Prayana7307 | ride_id: RD202509282014567B2C | duration_minutes: 45 | final_fare: 150.0 | destination_stall_id: STALL2025092612155912A0 | destination_stall_name: VIT Main Gate
```

### 4. Error Logs (`logs/errors.log`)
```
2025-09-30 14:35:12 | ERROR | ERROR BOOKING_CREATE_ERROR | Message: Bike not available | UserID: Prayana20250928201234ABCD | Endpoint: /api/bookings/create
2025-09-30 14:36:45 | ERROR | ERROR LOGIN_ERROR | Message: Database connection timeout | Endpoint: /api/auth/login
2025-09-30 14:36:45 | ERROR | Stack Trace:
Traceback (most recent call last):
  File "/home/clouduser/GEt/prayana/fast_app.py", line 425, in login
    user = User.objects(email=user_credentials.email).first()
  File "mongoengine/queryset/queryset.py", line 1756, in first
    result = self[:1]
...
```

### 5. System Logs (`logs/system.log`)
```
2025-09-30 14:00:00 | INFO | SYSTEM APPLICATION_STARTUP | service: Prayana FastAPI | version: 1.0.0
2025-09-30 14:00:01 | INFO | SYSTEM DATABASE_CONNECTED | host: localhost | port: 27017 | database: prayana
2025-09-30 16:30:15 | INFO | SYSTEM DAILY_CLEANUP | cleaned_records: 150 | operation: bike_location_cleanup
```

## Benefits of Normal Text Format

### ✅ **Human Readable**
- Easy to read and understand without tools
- Natural text format for quick debugging
- No need for JSON parsing to read logs

### ✅ **Grep Friendly**
- Simple text search with standard Unix tools
- Easy filtering and pattern matching
- Quick log analysis with basic commands

### ✅ **Compact**
- Smaller file sizes compared to JSON
- Less verbose than structured JSON format
- Efficient storage and faster processing

### ✅ **Debug Friendly**
- Stack traces displayed naturally
- Multi-line error information preserved
- Clear separation of different log components

## Log Analysis Commands

### View Recent Activity:
```bash
# View recent API requests
tail -f logs/api_requests.log

# View authentication events
tail -f logs/authentication.log

# Monitor booking activities
tail -f logs/bookings.log
```

### Search and Filter:
```bash
# Find failed login attempts
grep "LOGIN_FAILED" logs/authentication.log

# Find specific user activity
grep "UserID: Prayana20250928201234ABCD" logs/*.log

# Find booking activities for specific bike
grep "BikeID: Prayana7307" logs/bookings.log

# Find API errors
grep "ERROR" logs/errors.log

# Find specific booking
grep "BookingID: BK202509282014249BA0" logs/bookings.log
```

### Performance Analysis:
```bash
# Find slow API requests (over 1000ms)
grep "Duration: [0-9]\{4,\}ms" logs/api_requests.log

# Count requests by endpoint
grep "POST /api" logs/api_requests.log | wc -l

# Find successful bookings today
grep "$(date '+%Y-%m-%d')" logs/bookings.log | grep "BOOKING_CREATE_SUCCESS"
```

### Error Analysis:
```bash
# View recent errors with context
tail -n 100 logs/errors.log

# Find specific error types
grep "BOOKING_CREATE_ERROR" logs/errors.log

# Count errors by type
grep "ERROR" logs/errors.log | cut -d'|' -f3 | cut -d' ' -f2 | sort | uniq -c
```

## Log Rotation
- **File Size Limit**: 10MB per log file
- **Backup Files**: 30 previous versions kept
- **Naming**: `filename.log.1`, `filename.log.2`, etc.
- **Automatic**: Rotation happens automatically when size limit reached

## File Locations
```
logs/
├── api_requests.log      # All API request activity
├── authentication.log   # Login, signup, auth events
├── bookings.log         # Booking and ride operations
├── errors.log           # Application errors
├── system.log           # System events
├── api_requests.log.1   # Previous rotation files
├── authentication.log.1
└── ...
```

The normal text format provides excellent readability while maintaining all the essential information for debugging, monitoring, and analysis.