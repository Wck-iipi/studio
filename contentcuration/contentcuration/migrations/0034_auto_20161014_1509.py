# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-10-14 22:09
from __future__ import unicode_literals

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ('contentcuration', '0033_auto_20161012_1344'),
    ]

    operations = [
        migrations.AlterField(
            model_name='exercise',
            name='mastery_model',
            field=models.CharField(choices=[('do_all', 'Do all'), ('num_correct_in_a_row_10', '10 in a row'), ('num_correct_in_a_row_3', '3 in a row'), (
                'num_correct_in_a_row_5', '5 in a row'), ('skill_check', 'Skill check'), ('m_of_n', 'M out of N')], default='do_all', max_length=200),
        ),
        migrations.AlterField(
            model_name='fileformat',
            name='extension',
            field=models.CharField(choices=[('mp4', 'mp4'), ('vtt', 'vtt'), ('srt', 'srt'), ('mp3', 'mp3'), ('wav', 'wav'), ('pdf', 'pdf'), ('jpg', 'jpg'), (
                'jpeg', 'jpeg'), ('png', 'png'), ('json', 'json'), ('svg', 'svg'), ('perseus', 'perseus')], max_length=40, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='formatpreset',
            name='id',
            field=models.CharField(choices=[('high_res_video', 'High Resolution'), ('low_res_video', 'Low Resolution'), ('vector_video', 'Vectorized'), ('video_thumbnail', 'Thumbnail'), ('video_subtitle', 'Subtitle'), ('audio', 'Audio'), ('audio_thumbnail', 'Thumbnail'), (
                'document', 'Document'), ('document_thumbnail', 'Thumbnail'), ('exercise', 'Exercise'), ('exercise_thumbnail', 'Thumbnail'), ('exercise_image', 'Exercise Image'), ('exercise_graphie', 'Exercise Graphie')], max_length=150, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='formatpreset',
            name='order',
            field=models.IntegerField(default=0),
        ),
    ]
