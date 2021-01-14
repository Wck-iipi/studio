# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2020-09-15 18:39
from __future__ import unicode_literals

from django.db import migrations
from django.db import models

import contentcuration.models


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ('contentcuration', '0115_index_contentnode_node_id_field'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name="channel",
                    index=models.Index(fields=["name"], name="channel_name_idx"),
                ),
            ],
            database_operations=[
                # operation to run custom SQL command (check the output of `sqlmigrate`
                # to see the auto-generated SQL, edit as needed)
                migrations.RunSQL(
                    sql='CREATE INDEX CONCURRENTLY "{index_name}" ON "contentcuration_channel" ("name");'.format(
                        index_name=contentcuration.models.CHANNEL_NAME_INDEX_NAME
                    ),
                    reverse_sql='DROP INDEX "{index_name}"'.format(
                        index_name=contentcuration.models.CHANNEL_NAME_INDEX_NAME
                    ),
                ),
            ],
        ),

        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name="contentnode",
                    index=models.Index(
                        fields=["-modified"], name="node_modified_desc_idx"
                    ),
                ),
            ],
            database_operations=[
                # operation to run custom SQL command (check the output of `sqlmigrate`
                # to see the auto-generated SQL, edit as needed)
                migrations.RunSQL(
                    sql='CREATE INDEX CONCURRENTLY "{index_name}" ON "contentcuration_contentnode" (modified DESC NULLS LAST);'.format(
                        index_name=contentcuration.models.NODE_MODIFIED_DESC_INDEX_NAME
                    ),
                    reverse_sql='DROP INDEX "{index_name}"'.format(
                        index_name=contentcuration.models.NODE_MODIFIED_DESC_INDEX_NAME
                    ),
                ),
            ],
        ),

        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name="file",
                    index=models.Index(fields=['checksum', 'file_size'], name="file_checksum_file_size_idx"),
                ),
            ],
            database_operations=[
                # operation to run custom SQL command (check the output of `sqlmigrate`
                # to see the auto-generated SQL, edit as needed)
                migrations.RunSQL(
                    sql='CREATE INDEX CONCURRENTLY "{index_name}" ON "contentcuration_file" ("checksum", "file_size");'.format(
                        index_name=contentcuration.models.FILE_DISTINCT_INDEX_NAME
                    ),
                    reverse_sql='DROP INDEX "{index_name}"'.format(
                        index_name=contentcuration.models.FILE_DISTINCT_INDEX_NAME
                    ),
                ),
            ],
        ),

    ]
