# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'PendingTask'
        db.create_table(u'scheduler_pendingtask', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('task', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['scheduler.Task'])),
            ('scheduled_for', self.gf('django.db.models.fields.DateTimeField')()),
        ))
        db.send_create_signal(u'scheduler', ['PendingTask'])

        # Adding model 'Task'
        db.create_table(u'scheduler_task', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('account_id', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('label', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('task_type', self.gf('django.db.models.fields.CharField')(default='conversation-action', max_length=32)),
            ('task_data', self.gf('go.scheduler.models.JsonField')(default=None)),
            ('status', self.gf('django.db.models.fields.CharField')(default='pending', max_length=32)),
            ('scheduled_for', self.gf('django.db.models.fields.DateTimeField')()),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('started_timestamp', self.gf('django.db.models.fields.DateTimeField')(null=True)),
        ))
        db.send_create_signal(u'scheduler', ['Task'])


    def backwards(self, orm):
        # Deleting model 'PendingTask'
        db.delete_table(u'scheduler_pendingtask')

        # Deleting model 'Task'
        db.delete_table(u'scheduler_task')


    models = {
        u'scheduler.pendingtask': {
            'Meta': {'object_name': 'PendingTask'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'scheduled_for': ('django.db.models.fields.DateTimeField', [], {}),
            'task': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['scheduler.Task']"})
        },
        u'scheduler.task': {
            'Meta': {'object_name': 'Task'},
            'account_id': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'label': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'scheduled_for': ('django.db.models.fields.DateTimeField', [], {}),
            'started_timestamp': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'pending'", 'max_length': '32'}),
            'task_data': ('go.scheduler.models.JsonField', [], {'default': 'None'}),
            'task_type': ('django.db.models.fields.CharField', [], {'default': "'conversation-action'", 'max_length': '32'})
        }
    }

    complete_apps = ['scheduler']