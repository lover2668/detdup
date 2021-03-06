# -*- coding: utf-8 -*-

from peewee import SqliteDatabase, Model, CharField, BooleanField, TextField, TimeField
import os
import datetime


class FakeItemIds(object):
    """
    Manage fake item ids and their cache and index.

    Client send item with no item id, so we need to make a fake item id for it, cause index db need one.

    TODO: while just not delete it after query immediately, not until the next query coming.
    """

    def __init__(self, data_model):
        self.data_model = data_model
        self.data_model.fake_item_ids_store = self

        assert self.data_model.cache_dir, "FakeItemIds need cache_dir from data_model!"
        sqlite_path = os.path.join(self.data_model.cache_dir, "fake_item_ids_store.db")

        sqlite_database = SqliteDatabase(sqlite_path, check_same_thread=False)

        class FakeItemIdsStore(Model):
            is_deleted = BooleanField(default=False)  # mark processed or duplicated items
            item_id = CharField()
            item_content_json = TextField()
            created_at = TimeField(default=datetime.datetime.now)

            class Meta:
                database = sqlite_database
        self.storage = FakeItemIdsStore

        if not self.storage.table_exists():
            self.storage.create_table()
            sqlite_database.create_index(self.storage, "is_deleted item_id".split(" "))

    def insert(self, item_id, item_content_json=None):
        self.storage.create(item_id=item_id,
                            item_content_json=item_content_json)

    def remove(self, item_id):
        print "[删除]", item_id
        # 1. 软删除 fake_item_ids_store 记录
        self.storage.update(is_deleted=True).where(self.storage.item_id == str(item_id)).execute()

        # 2. 从feature索引中删除
        item1 = self.data_model.get(item_id, None)
        if item1 is None:
            return False  # compact with unkonw error TODO 20150430
        table = self.data_model.core.select_feature(item1).features_tree
        table.delete().where(table.item_id == str(item_id)).execute()

        # 3. 从items_model中删除
        del self.data_model[item_id]
        return True

    def remove_all(self):
        delete_scope = self.storage.select().where(
            self.storage.is_deleted == eval("False"))  # compact with PEP E712
        for i1 in delete_scope:
            self.remove(i1.item_id)
