"""撤销/重做管理器 —— 用于版本、预算、风险 CRUD 的 Ctrl+Z / Ctrl+Y"""
import json
from collections import deque


class UndoManager:
    def __init__(self, max_size=20):
        self.undo_stack = deque(maxlen=max_size)
        self.redo_stack = deque(maxlen=max_size)

    def record(self, action_desc, undo_sql, undo_params, redo_sql, redo_params):
        entry = {
            "desc": action_desc,
            "undo_sql": undo_sql,
            "undo_params": undo_params,
            "redo_sql": redo_sql,
            "redo_params": redo_params,
            "reversible": True,
        }
        self.undo_stack.append(entry)
        self.redo_stack.clear()

    def record_insert(self, table, row_data, action_desc="插入"):
        columns = ", ".join(row_data.keys())
        placeholders = ", ".join(["?"] * len(row_data))
        values = list(row_data.values())
        self.record(
            action_desc,
            f"DELETE FROM {table} WHERE " + " AND ".join([f"{k}=?" for k in row_data.keys()]),
            values,
            f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})",
            values,
        )

    def record_delete(self, table, old_data, action_desc="删除"):
        columns = ", ".join(old_data.keys())
        placeholders = ", ".join(["?"] * len(old_data))
        values = list(old_data.values())
        self.record(
            action_desc,
            f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})",
            values,
            f"DELETE FROM {table} WHERE " + " AND ".join([f"{k}=?" for k in old_data.keys()]),
            values,
        )

    def record_update(self, table, old_data, new_data, action_desc="更新"):
        set_clause = ", ".join([f"{k}=?" for k in new_data.keys() if k in old_data])
        where_clause = " AND ".join([f"{k}=?" for k in old_data.keys()])
        undo_values = list(old_data.values())
        redo_values = list(new_data[k] for k in old_data.keys() if k in new_data) + list(old_data.values())
        self.record(
            action_desc,
            f"UPDATE {table} SET {set_clause} WHERE {where_clause}",
            undo_values,
            f"UPDATE {table} SET {set_clause} WHERE {where_clause}",
            redo_values,
        )

    def can_undo(self):
        return len(self.undo_stack) > 0

    def can_redo(self):
        return len(self.redo_stack) > 0

    def undo(self, conn):
        if not self.undo_stack:
            return None
        entry = self.undo_stack.pop()
        try:
            conn.execute(entry["undo_sql"], entry["undo_params"])
            conn.commit()
            self.redo_stack.append(entry)
            return entry["desc"]
        except Exception as e:
            self.undo_stack.append(entry)
            raise e

    def redo(self, conn):
        if not self.redo_stack:
            return None
        entry = self.redo_stack.pop()
        try:
            conn.execute(entry["redo_sql"], entry["redo_params"])
            conn.commit()
            self.undo_stack.append(entry)
            return entry["desc"]
        except Exception as e:
            self.redo_stack.append(entry)
            raise e


_undo_manager = UndoManager()


def get_undo_manager():
    return _undo_manager
