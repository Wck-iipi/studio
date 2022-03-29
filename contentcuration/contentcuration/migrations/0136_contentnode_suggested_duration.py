# Generated by Django 3.2.5 on 2022-03-21 21:40
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ('contentcuration', '0135_add_metadata_labels'),
    ]

    operations = [
        migrations.AddField(
            model_name='contentnode',
            name='suggested_duration',
            field=models.IntegerField(blank=True, help_text='Suggested duration for the content node (in seconds)', null=True),
        ),
    ]