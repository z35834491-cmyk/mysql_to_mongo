import pymysql
import redis
import pymongo
import pika
import json
import datetime
import random

def inject_mysql():
    print("Injecting MySQL Data...")
    try:
        # Assuming default credentials from typical docker setup or generic
        conn = pymysql.connect(
            host='localhost',
            port=3317,
            user='root',
            password='root', # Correct password found from docker inspect
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        with conn.cursor() as cursor:
            cursor.execute("CREATE DATABASE IF NOT EXISTS testdb")
            cursor.execute("USE testdb")
            
            # Complex Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS complex_orders (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    order_code VARCHAR(50),
                    customer_info JSON,
                    items JSON,
                    status ENUM('PENDING', 'PAID', 'SHIPPED', 'DELIVERED', 'CANCELLED'),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT
                )
            """)
            
            # Insert Data
            statuses = ['PENDING', 'PAID', 'SHIPPED', 'DELIVERED', 'CANCELLED']
            for i in range(20):
                customer = {
                    "name": f"User {i}",
                    "address": {
                        "street": f"{i} Main St",
                        "city": "Tech City",
                        "zip": f"1000{i}"
                    },
                    "tags": ["vip" if i % 3 == 0 else "regular", "new"]
                }
                items = [
                    {"product_id": random.randint(100, 200), "qty": random.randint(1, 5), "price": random.uniform(10, 500)}
                    for _ in range(random.randint(1, 4))
                ]
                
                sql = "INSERT INTO complex_orders (order_code, customer_info, items, status, notes) VALUES (%s, %s, %s, %s, %s)"
                cursor.execute(sql, (
                    f"ORD-{2024000+i}",
                    json.dumps(customer),
                    json.dumps(items),
                    random.choice(statuses),
                    "Lorem ipsum dolor sit amet, consectetur adipiscing elit." if i % 2 == 0 else ""
                ))
            
            conn.commit()
            print("MySQL: Inserted 20 complex rows.")
    except Exception as e:
        print(f"MySQL Error: {e}")

def inject_redis():
    print("Injecting Redis Data...")
    try:
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        
        # 1. Complex Hash (Session)
        for i in range(5):
            r.hset(f"session:user:{1000+i}", mapping={
                "id": 1000+i,
                "name": f"User {i}",
                "preferences": json.dumps({"theme": "dark", "notifications": True}),
                "last_access": datetime.datetime.now().isoformat(),
                "cart_items": random.randint(0, 10)
            })
            
        # 2. List (Logs)
        for i in range(10):
            log_entry = json.dumps({
                "level": "INFO" if i % 4 != 0 else "ERROR",
                "timestamp": datetime.datetime.now().isoformat(),
                "message": f"Operation {i} completed",
                "module": "auth_service"
            })
            r.lpush("system:logs", log_entry)
            
        # 3. Set (Tags)
        r.sadd("global:tags", "featured", "sale", "new_arrival", "clearance", "summer_2024")
        
        # 4. Sorted Set (Leaderboard)
        for i in range(10):
            r.zadd("game:leaderboard", {f"Player_{i}": random.randint(1000, 5000)})
            
        print("Redis: Inserted Hashes, Lists, Sets, ZSets.")
    except Exception as e:
        print(f"Redis Error: {e}")

def inject_mongo():
    print("Injecting MongoDB Data...")
    try:
        # Port 27018 based on docker ps
        # directConnection=true is needed because the replica set members (mongo1, etc.) are not resolvable from host
        # Added authSource=admin and credentials
        client = pymongo.MongoClient("mongodb://root:root@localhost:27018/?directConnection=true&authSource=admin")
        db = client["ecommerce"]
        collection = db["products"]
        
        # Drop to clean
        collection.drop()
        
        products = []
        categories = ["Electronics", "Home", "Fashion", "Books"]
        
        for i in range(15):
            product = {
                "name": f"Product {i}",
                "category": random.choice(categories),
                "price": round(random.uniform(10, 999), 2),
                "specs": {
                    "weight": f"{random.randint(100, 2000)}g",
                    "dimensions": {
                        "l": random.randint(10, 50),
                        "w": random.randint(10, 50),
                        "h": random.randint(1, 20)
                    },
                    "features": ["wireless", "bluetooth", "smart"] if i % 2 == 0 else ["eco-friendly", "handmade"]
                },
                "reviews": [
                    {"user": "Alice", "rating": 5, "comment": "Great!"},
                    {"user": "Bob", "rating": 4, "comment": "Good value."}
                ],
                "stock_history": [100, 95, 80, 50, 20],
                "is_active": True,
                "created_at": datetime.datetime.now()
            }
            products.append(product)
            
        collection.insert_many(products)
        print("MongoDB: Inserted 15 complex documents.")
        
    except Exception as e:
        print(f"MongoDB Error: {e}")

def inject_rabbitmq():
    print("Injecting RabbitMQ Data...")
    try:
        credentials = pika.PlainCredentials('guest', 'guest')
        parameters = pika.ConnectionParameters('localhost', 5672, '/', credentials)
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        
        # Declare queues
        channel.queue_declare(queue='transaction_events', durable=True)
        channel.queue_declare(queue='email_notifications', durable=True)
        
        # 1. Transaction Events (Complex JSON)
        for i in range(5):
            body = {
                "tx_id": f"TX-{random.randint(10000, 99999)}",
                "amount": random.uniform(100, 5000),
                "currency": "USD",
                "merchant": {
                    "id": "M-55",
                    "name": "SuperStore"
                },
                "flags": ["fraud_check_passed", "high_value"] if i == 0 else []
            }
            
            channel.basic_publish(
                exchange='',
                routing_key='transaction_events',
                body=json.dumps(body),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                    content_type='application/json',
                    headers={'source': 'payment_gateway', 'version': 'v2'}
                ))
        
        # 2. Email Notifications
        for i in range(3):
            body = {
                "to": f"user{i}@example.com",
                "subject": "Your Order Update",
                "template": "order_shipped",
                "context": {"order_id": 12345, "tracking": "XXYYZZ"}
            }
            channel.basic_publish(
                exchange='',
                routing_key='email_notifications',
                body=json.dumps(body),
                properties=pika.BasicProperties(
                    content_type='application/json',
                    priority=10 if i == 0 else 5
                ))
                
        connection.close()
        print("RabbitMQ: Published messages to 'transaction_events' and 'email_notifications'.")
    except Exception as e:
        print(f"RabbitMQ Error: {e}")

if __name__ == "__main__":
    inject_mysql()
    inject_redis()
    inject_mongo()
    inject_rabbitmq()
