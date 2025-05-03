# Webhook Delivery Service

A robust backend system that functions as a reliable webhook delivery service. This service ingests incoming webhooks, queues them, and attempts delivery to subscribed target URLs, handling failures with retries and providing visibility into the delivery status.

## Architecture

The service is built using:
- **FastAPI**: Modern, fast web framework for building APIs
- **PostgreSQL**: Relational database for storing subscriptions and delivery logs
- **Redis**: In-memory data store for caching and task queue
- **Celery**: Distributed task queue for asynchronous processing
- **Docker**: Containerization for easy deployment and scaling

### Key Components

1. **Web Service (FastAPI)**
   - Handles HTTP requests
   - Manages subscriptions
   - Ingests webhooks
   - Provides status/analytics endpoints

2. **Worker Service (Celery)**
   - Processes webhook deliveries
   - Implements retry mechanism
   - Handles cleanup tasks

3. **Database (PostgreSQL)**
   - Stores subscriptions
   - Maintains delivery logs
   - Implements data retention

4. **Cache (Redis)**
   - Caches subscription details
   - Manages task queue
   - Improves performance

## Database Schema

### Tables

1. **subscriptions**
   - `id`: Primary key
   - `target_url`: Webhook destination
   - `secret`: HMAC secret for signature verification
   - `event_types`: JSON array of subscribed events
   - `is_active`: Boolean flag
   - `created_at`: Timestamp
   - `updated_at`: Timestamp

2. **webhooks**
   - `id`: Primary key
   - `subscription_id`: Foreign key to subscriptions
   - `payload`: JSON payload
   - `event_type`: Event type
   - `created_at`: Timestamp

3. **delivery_attempts**
   - `id`: Primary key
   - `subscription_id`: Foreign key to subscriptions
   - `webhook_id`: Foreign key to webhooks
   - `attempt_number`: Retry count
   - `status_code`: HTTP response code
   - `response_body`: Response content
   - `error_message`: Error details
   - `is_success`: Boolean flag
   - `created_at`: Timestamp

### Indexes

- `ix_subscriptions_is_active`: Optimizes active subscription queries
- `ix_subscriptions_event_types`: GIN index for event type filtering
- `ix_delivery_attempts_subscription_id`: Optimizes subscription history queries
- `ix_delivery_attempts_webhook_id`: Optimizes webhook delivery tracking
- `ix_delivery_attempts_created_at`: Optimizes retention cleanup
- `ix_delivery_attempts_is_success`: Optimizes success/failure queries
- `ix_webhooks_subscription_id`: Optimizes subscription webhook queries
- `ix_webhooks_event_type`: Optimizes event type filtering
- `ix_webhooks_created_at`: Optimizes time-based queries

## Setup Instructions

1. **Prerequisites**
   - Docker
   - Docker Compose

2. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd WebHook_Service
   ```

3. **Start Services**
   ```bash
   docker-compose up --build
   ```

4. **Access Services**
   - Web API: http://localhost:8081
   - API Documentation: http://localhost:8081/docs
   - Test Server: http://localhost:9000

## Live Demo

A live demo of this service is hosted on an AWS EC2 instance and is accessible at:

- **Web Service:** [http://13.50.109.88:8081](http://13.50.109.88:8081)
- **API Documentation:** [http://13.50.109.88:8081/docs](http://13.50.109.88:8081/docs)
- **Test Server:** [http://13.50.109.88:9000](http://13.50.109.88:9000)

### Using the Live Demo

1. **Create a Webhook Subscription**
   - Visit [http://13.50.109.88:8081](http://13.50.109.88:8081)
   - Click on "Create Subscription"
   - Set the Target URL to `http://13.50.109.88:9000/test` to use the test server
   - Add event types (e.g., "test_event")
   - Provide a description (optional)
   - Submit the form

2. **Trigger a Webhook Event**
   - Click on "Send Webhook"
   - Select the event type you subscribed to
   - Enter a JSON payload (e.g., `{"message": "Hello from webhook!"}`)
   - Send the event

3. **View Results**
   - Check "Active Subscriptions" to see your webhook
   - View "Delivery History" to see delivery status and responses
   - The test server will display received webhooks at [http://13.50.109.88:9000](http://13.50.109.88:9000)

The demo instance is hosted on AWS EC2 using Docker Compose to orchestrate all the necessary services including PostgreSQL database, Redis cache, Celery workers, and the web application.

## Sample API Usage

1. **Create Subscription**
   ```bash
   curl -X POST http://localhost:8081/subscriptions \
     -H "Content-Type: application/json" \
     -d '{
       "target_url": "http://host.docker.internal:9000/webhook",
       "secret": "supersecret",
       "event_types": ["user.created"]
     }'
   ```

2. **Ingest Webhook**
   ```bash
   curl -X POST http://localhost:8081/ingest/1 \
     -H "Content-Type: application/json" \
     -d '{
       "payload": {"user_id": 123, "name": "John Doe"},
       "event_type": "user.created"
     }'
   ```

3. **Check Delivery Attempts**
   ```bash
   curl http://localhost:8081/delivery-attempts/1
   ```

## Cost Estimation

Assuming deployment on AWS Free Tier:

1. **EC2 t2.micro**
   - Free for 12 months
   - 1 vCPU, 1GB RAM
   - Estimated cost after free tier: $8.56/month

2. **RDS PostgreSQL**
   - Free for 12 months
   - db.t2.micro
   - 20GB storage
   - Estimated cost after free tier: $15.00/month

3. **ElastiCache Redis**
   - Free for 12 months
   - cache.t2.micro
   - Estimated cost after free tier: $12.00/month

**Total Estimated Monthly Cost (after free tier): $35.56**

## Assumptions

1. **Traffic Volume**
   - 5,000 webhooks per day
   - Average 1.2 delivery attempts per webhook
   - Peak load: 10 webhooks per second

2. **Data Retention**
   - Delivery logs retained for 72 hours
   - Cleanup task runs hourly

3. **Error Handling**
   - Maximum 5 retry attempts
   - Exponential backoff: 10s, 30s, 1m, 5m, 15m
   - Timeout: 10 seconds per attempt

4. **Security**
   - HMAC-SHA256 for signature verification
   - HTTPS for all external communications
   - Environment variables for sensitive data

## Credits

- FastAPI: https://fastapi.tiangolo.com/
- Celery: https://docs.celeryq.dev/
- PostgreSQL: https://www.postgresql.org/
- Redis: https://redis.io/
- Docker: https://www.docker.com/
