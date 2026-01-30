import pymysql
import redis
from redis.cluster import RedisCluster
from pymongo import MongoClient
import pika
import json
from bson import ObjectId
from datetime import datetime
from .models import DatabaseConnection

def mongo_json_default(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)

class DBEngineFactory:
    @staticmethod
    def get_engine(conn: DatabaseConnection):
        if conn.type == 'mysql':
            return MySQLEngine(conn)
        elif conn.type == 'redis':
            return RedisEngine(conn)
        elif conn.type == 'mongo':
            return MongoEngine(conn)
        elif conn.type == 'rabbitmq':
            return RabbitMQEngine(conn)
        else:
            raise ValueError(f"Unsupported database type: {conn.type}")

class BaseEngine:
    def __init__(self, conn: DatabaseConnection):
        self.conn = conn

    def test(self):
        raise NotImplementedError

    def get_structure(self):
        """Return tree: { db: [tables/collections] }"""
        raise NotImplementedError

    def query(self, db, target, query_params):
        """Return { headers: [], rows: [] }"""
        raise NotImplementedError

class MySQLEngine(BaseEngine):
    def _connect(self, db=None):
        return pymysql.connect(
            host=self.conn.host,
            port=self.conn.port,
            user=self.conn.user,
            password=self.conn.password,
            database=db or self.conn.database,
            connect_timeout=5,
            read_timeout=10,
            write_timeout=10,
            cursorclass=pymysql.cursors.DictCursor
        )

    def test(self):
        try:
            c = self._connect()
            c.close()
            return True, "Connected successfully"
        except Exception as e:
            return False, str(e)

    def get_structure(self):
        tree = {}
        conn = self._connect()
        try:
            with conn.cursor() as c:
                # Query information_schema for detailed table info
                c.execute("""
                    SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_ROWS, DATA_LENGTH, ENGINE, CREATE_TIME, UPDATE_TIME
                    FROM information_schema.TABLES 
                    WHERE TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema', 'sys', 'mysql')
                """)
                for row in c.fetchall():
                    db = row['TABLE_SCHEMA']
                    if db not in tree:
                        tree[db] = []
                    
                    # Format size
                    size = row['DATA_LENGTH'] or 0
                    if size > 1024 * 1024:
                        size_str = f"{size / (1024 * 1024):.2f} MB"
                    elif size > 1024:
                        size_str = f"{size / 1024:.2f} KB"
                    else:
                        size_str = f"{size} B"

                    tree[db].append({
                        "name": row['TABLE_NAME'],
                        "rows": row['TABLE_ROWS'],
                        "size": size_str,
                        "engine": row['ENGINE'],
                        "created": row['CREATE_TIME'].strftime('%Y-%m-%d %H:%M:%S') if row['CREATE_TIME'] else '-',
                        "updated": row['UPDATE_TIME'].strftime('%Y-%m-%d %H:%M:%S') if row['UPDATE_TIME'] else '-'
                    })
        finally:
            conn.close()
        return tree

    def query(self, db, table, params):
        sql = params.get('sql')
        where = params.get('where')
        conn = self._connect(db)
        try:
            with conn.cursor() as c:
                if sql:
                    # Execute multiple statements
                    try:
                        # Split statements if needed or rely on pymysql's ability
                        # Pymysql executes one statement at a time with .execute(), but we want to show results.
                        # For simplicity in this console, we execute and fetch result of the LAST statement or all if possible.
                        # However, standard cursor.execute() usually handles one statement unless client flags are set.
                        # We will try to execute it directly.
                        c.execute(sql)
                        
                        # Commit if it's a DML/DDL (Insert, Update, Delete, Create, Drop)
                        conn.commit()
                        
                        if c.description:
                            # It's a SELECT or similar returning rows
                            rows = c.fetchall()
                            rows = json.loads(json.dumps(rows, default=mongo_json_default))
                            headers = list(rows[0].keys()) if rows else ["Info"]
                            if not rows:
                                return {"headers": ["Info"], "rows": [{"Info": "Query executed successfully. No rows returned."}], "total": 0}
                            return {"headers": headers, "rows": rows, "total": len(rows)}
                        else:
                            # It's an INSERT/UPDATE/DELETE/DDL
                            msg = f"Query executed successfully. Affected rows: {c.rowcount}"
                            return {"headers": ["Info"], "rows": [{"Info": msg}], "total": 0}
                            
                    except Exception as e:
                        return {"headers": ["Error"], "rows": [{"Error": str(e)}], "total": 0}
                else:
                    page = int(params.get('page', 1))
                    page_size = int(params.get('pageSize', 100))
                    offset = (page - 1) * page_size
                    
                    count_sql = f"SELECT COUNT(*) as cnt FROM `{table}`"
                    if where: count_sql += f" WHERE {where}"
                    c.execute(count_sql)
                    total = c.fetchone()['cnt']
                    
                    select_sql = f"SELECT * FROM `{table}`"
                    if where: select_sql += f" WHERE {where}"
                    select_sql += " LIMIT %s OFFSET %s"
                    
                    c.execute(select_sql, (page_size, offset))
                    rows = c.fetchall()
                    if not rows:
                        return {"headers": [], "rows": [], "total": total}
                    
                    rows = json.loads(json.dumps(rows, default=mongo_json_default))
                    headers = list(rows[0].keys())
                    return {"headers": headers, "rows": rows, "total": total}
        finally:
            conn.close()

class RedisEngine(BaseEngine):
    def _connect(self, db=0):
        mode = self.conn.extra_config.get('mode', 'standalone')
        
        if mode == 'cluster':
            nodes = []
            if ',' in self.conn.host:
                for hp in self.conn.host.split(','):
                    try:
                        h, p = hp.split(':')
                        nodes.append(redis.cluster.ClusterNode(h, int(p)))
                    except: pass
            else:
                nodes.append(redis.cluster.ClusterNode(self.conn.host, self.conn.port))
            
            return RedisCluster(startup_nodes=nodes, password=self.conn.password or None, decode_responses=True)
        else:
            return redis.Redis(
                host=self.conn.host,
                port=self.conn.port,
                password=self.conn.password or None,
                db=db,
                socket_timeout=5,
                decode_responses=True
            )

    def test(self):
        try:
            r = self._connect()
            r.ping()
            r.close()
            return True, "Connected successfully"
        except Exception as e:
            return False, str(e)

    def get_structure(self):
        tree = {}
        r = self._connect()
        mode = self.conn.extra_config.get('mode', 'standalone')
        try:
            if mode == 'cluster':
                tree['db0'] = ['Keys']
            else:
                info = r.info('keyspace')
                for k in info.keys():
                    if k.startswith('db'):
                        tree[k] = ['Keys'] 
        except:
            tree['db0'] = ['Keys']
        finally:
            r.close()
        return tree

    def query(self, db_name, table, params):
        command = params.get('command')
        db_idx = int(db_name.replace('db', ''))
        
        mode = self.conn.extra_config.get('mode', 'standalone')
        if mode == 'cluster': db_idx = 0
            
        r = self._connect(db_idx)
        try:
            if command:
                parts = command.split()
                if not parts: return {"headers": [], "rows": [], "total": 0}
                cmd = parts[0]
                args = parts[1:]
                res = r.execute_command(cmd, *args)
                return {
                    "headers": ["Result"], 
                    "rows": [{"Result": str(res)}], 
                    "total": 1
                }
            
            pattern = params.get('pattern', '*')
            cursor, keys = r.scan(cursor=0, match=pattern, count=1000)
            
            rows = []
            for k in keys:
                try:
                    type_ = r.type(k)
                    val = "(large/complex)"
                    if type_ == 'string':
                        val = r.get(k)
                        if val and len(val) > 200: val = val[:200] + "..."
                    rows.append({"key": k, "type": type_, "value": val})
                except:
                    pass
                
            return {
                "headers": ["key", "type", "value"],
                "rows": rows,
                "total": len(rows),
            }
        finally:
            r.close()

class MongoEngine(BaseEngine):
    def _connect(self):
        if '://' in self.conn.host:
             return MongoClient(self.conn.host, serverSelectionTimeoutMS=5000)
        
        # Build URI
        creds = ""
        if self.conn.user:
            creds = f"{self.conn.user}:{self.conn.password}@"
            
        default_db = self.conn.database if self.conn.database else 'admin'
        
        # Check if authSource is provided in extra_config
        auth_source = 'admin'
        if self.conn.extra_config and self.conn.extra_config.get('authSource'):
            auth_source = self.conn.extra_config['authSource']
            
        # Construct base URI
        uri = f"mongodb://{creds}{self.conn.host}:{self.conn.port}/{default_db}?authSource={auth_source}"
        
        # Optional: Add directConnection=true ONLY if user explicitly requested it or if we detect it might be needed.
        # But user said "I don't need forced". So we remove forced directConnection.
        # If user is connecting to a specific member of a replica set from outside (like via SSH tunnel or Docker port mapping),
        # they might actually NEED directConnection=true, but let's respect the "standard" behavior first.
        # If it fails, user can use URI string mode to customize.
        
        return MongoClient(uri, serverSelectionTimeoutMS=5000)

    def test(self):
        try:
            c = self._connect()
            c.server_info()
            c.close()
            return True, "Connected"
        except Exception as e:
            return False, str(e)

    def get_structure(self):
        tree = {}
        c = self._connect()
        try:
            # Check if connected
            c.admin.command('ping')
            
            dbs = c.list_database_names()
            for db in dbs:
                if db in ('admin', 'config', 'local'): continue
                cols = c[db].list_collection_names()
                
                col_list = []
                for col_name in cols:
                    try:
                        stats = c[db].command("collStats", col_name)
                        size = stats.get('size', 0)
                        if size > 1024 * 1024:
                            size_str = f"{size / (1024 * 1024):.2f} MB"
                        elif size > 1024:
                            size_str = f"{size / 1024:.2f} KB"
                        else:
                            size_str = f"{size} B"
                            
                        col_list.append({
                            "name": col_name,
                            "rows": stats.get('count', 0),
                            "size": size_str,
                            "engine": "WiredTiger",
                            "created": "-", 
                            "updated": "-" 
                        })
                    except:
                         col_list.append({
                            "name": col_name,
                            "rows": "-",
                            "size": "-",
                            "engine": "-",
                            "created": "-",
                            "updated": "-"
                        })
                tree[db] = col_list
        finally:
            c.close()
        return tree

    def query(self, db, collection, params):
        filter_str = params.get('filter')
        c = self._connect()
        try:
            col = c[db][collection]
            
            if filter_str:
                try:
                    query_filter = json.loads(filter_str)
                except:
                    return {"headers": ["Error"], "rows": [{"Error": "Invalid JSON"}], "total": 0}
                cursor = col.find(query_filter).limit(50)
                total = 50
            else:
                page = int(params.get('page', 1))
                page_size = int(params.get('pageSize', 20))
                skip = (page - 1) * page_size
                cursor = col.find().skip(skip).limit(page_size)
                total = col.estimated_document_count()
            
            rows = []
            for doc in cursor:
                safe_doc = json.loads(json.dumps(doc, default=mongo_json_default))
                rows.append(safe_doc)
            
            headers = set()
            for r in rows:
                headers.update(r.keys())
            
            return {"headers": list(headers), "rows": rows, "total": total}
        finally:
            c.close()

class RabbitMQEngine(BaseEngine):
    def _connect(self):
        credentials = pika.PlainCredentials(self.conn.user, self.conn.password)
        vhost = self.conn.database or '/'
        params = pika.ConnectionParameters(
            host=self.conn.host,
            port=self.conn.port or 5672,
            virtual_host=vhost,
            credentials=credentials,
            socket_timeout=5
        )
        return pika.BlockingConnection(params)

    def test(self):
        try:
            c = self._connect()
            c.close()
            return True, "Connected successfully"
        except Exception as e:
            return False, str(e)
    
    def get_structure(self):
        return {"Queues": ["(Enter Queue Name)"]}
        
    def query(self, db, target, params):
        queue_name = params.get('where') or target
        if queue_name == "(Enter Queue Name)" or not queue_name:
             return {"headers": ["Info"], "rows": [{"Info": "Please enter Queue Name in search box"}], "total": 0}
             
        conn = self._connect()
        try:
            channel = conn.channel()
            rows = []
            for _ in range(10):
                method, props, body = channel.basic_get(queue_name, auto_ack=False)
                if method:
                    rows.append({
                        "Exchange": method.exchange,
                        "RoutingKey": method.routing_key,
                        "Redelivered": method.redelivered,
                        "Body": body.decode('utf-8', 'ignore')[:500]
                    })
                else:
                    break
            return {"headers": ["Exchange", "RoutingKey", "Body", "Redelivered"], "rows": rows, "total": len(rows)}
        except Exception as e:
            return {"headers": ["Error"], "rows": [{"Error": str(e)}], "total": 0}
        finally:
            conn.close()
