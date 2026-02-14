# app/sync/mongo_writer.py
import time
import random
from collections import Counter
from typing import List

from pymongo.errors import BulkWriteError, AutoReconnect, OperationFailure
from core.logging import log


class MongoWriter:
    def __init__(self, task_id: str, stop_event):
        self.task_id = task_id
        self.stop_event = stop_event
        self._indexed_collections = set ()

    def _ensure_custom_indexes(self, coll, table: str, coll_name: str):
        #新表自定义索引，已存在直接跳。
        if coll_name in self._indexed_collections:
            return


        custom_indexes = [
            IndexModel([("updated_at", DESCENDING)], background=True),
            IndexModel([("status", ASCENDING), ("created_at", DESCENDING)], background=True)
            # 按照上面的格式可以添加修改索引，第一行是但字段，第二行是联合
        ]

        try:
            # 如果索引已存在会直接返回成功
            coll.create_indexes(custom_indexes)
            self._indexed_collections.add(coll_name)
            log(self.task_id, f"Ensured custom indexes for t={table} c={coll_name}")
        except OperationFailure as e:
            # 捕捉一些基础报错
            log(self.task_id, f"Failed to create indexes t={table} c={coll_name}: {str(e)[:180]}")
            # 失败加入 set 中
            self._indexed_collections.add(coll_name)

    def _log_bulk_error(self, table: str, coll_name: str, write_errors: List[dict], max_samples: int = 3):
        code_counter = Counter()
        samples = []
        # Count all codes
        for w in write_errors:
            code = w.get("code")
            code_counter[code] += 1

        # Sample messages
        for w in write_errors[:max_samples]:
            code = w.get("code")
            msg = (w.get("errmsg") or "")[:180]
            idx = w.get("index")
            samples.append(f"idx={idx} code={code} msg={msg}")

        log(
            self.task_id,
            f"BulkWriteError t={table} c={coll_name} errors={len(write_errors)} codes={dict(code_counter)} samples={samples}",
        )

    def safe_bulk_write(self, coll, ops: List, table: str, coll_name: str, max_retry: int = 6) -> bool:
        if not ops:
            return True
        # 确认索引已经创建。
        self._ensure_custom_indexes(coll, table, coll_name)

        backoff = 1.0
        for _ in range(max_retry):
            if self.stop_event.is_set():
                return False
            try:
                coll.bulk_write(ops, ordered=False)
                return True
            except BulkWriteError as e:
                details = e.details or {}
                write_errors = details.get("writeErrors", []) or []

                only_dup = (len(write_errors) > 0) and all(w.get("code") == 11000 for w in write_errors)
                if only_dup:
                    return True

                self._log_bulk_error(table, coll_name, write_errors)

                has_215 = any(w.get("code") == 215 for w in write_errors)
                if not has_215:
                    return False
            except (AutoReconnect, OperationFailure) as e:
                log(self.task_id, f"Mongo transient error: {str(e)[:180]}")

            time.sleep(min(30.0, backoff) + random.random() * 0.2)
            backoff *= 2

        log(self.task_id, f"Mongo write failed after retries t={table} c={coll_name} batch={len(ops)}")
        return False
