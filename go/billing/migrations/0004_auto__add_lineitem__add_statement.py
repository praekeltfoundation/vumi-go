# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'LineItem'
        db.create_table(u'billing_lineitem', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('statement', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['billing.Statement'])),
            ('tag_pool_name', self.gf('django.db.models.fields.CharField')(default='', max_length=100, blank=True)),
            ('tag_name', self.gf('django.db.models.fields.CharField')(default='', max_length=100, blank=True)),
            ('message_direction', self.gf('django.db.models.fields.CharField')(default='', max_length=20, blank=True)),
            ('total_cost', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal(u'billing', ['LineItem'])

        # Adding model 'Statement'
        db.create_table(u'billing_statement', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('account', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['billing.Account'])),
            ('title', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('from_date', self.gf('django.db.models.fields.DateField')()),
            ('to_date', self.gf('django.db.models.fields.DateField')()),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
        ))
        db.send_create_signal(u'billing', ['Statement'])


    def backwards(self, orm):
        # Deleting model 'LineItem'
        db.delete_table(u'billing_lineitem')

        # Deleting model 'Statement'
        db.delete_table(u'billing_statement')


    models = {
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'base.gouser': {
            'Meta': {'object_name': 'GoUser'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'unique': 'True', 'max_length': '254'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '254'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '254'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'billing.account': {
            'Meta': {'object_name': 'Account'},
            'account_number': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'}),
            'alert_credit_balance': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'alert_threshold': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '10', 'decimal_places': '2'}),
            'credit_balance': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['base.GoUser']"})
        },
        u'billing.lineitem': {
            'Meta': {'object_name': 'LineItem'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'message_direction': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '20', 'blank': 'True'}),
            'statement': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['billing.Statement']"}),
            'tag_name': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100', 'blank': 'True'}),
            'tag_pool_name': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100', 'blank': 'True'}),
            'total_cost': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'billing.messagecost': {
            'Meta': {'object_name': 'MessageCost'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['billing.Account']", 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'markup_percent': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '10', 'decimal_places': '2'}),
            'message_cost': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'message_direction': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'tag_pool': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['billing.TagPool']"})
        },
        u'billing.statement': {
            'Meta': {'object_name': 'Statement'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['billing.Account']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'from_date': ('django.db.models.fields.DateField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'to_date': ('django.db.models.fields.DateField', [], {})
        },
        u'billing.tagpool': {
            'Meta': {'object_name': 'TagPool'},
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'})
        },
        u'billing.transaction': {
            'Meta': {'object_name': 'Transaction'},
            'account_number': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'credit_amount': ('django.db.models.fields.IntegerField', [], {}),
            'credit_factor': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '10', 'decimal_places': '2', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'markup_percent': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '10', 'decimal_places': '2', 'blank': 'True'}),
            'message_cost': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'message_direction': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'Pending'", 'max_length': '20'}),
            'tag_name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'tag_pool_name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        }
    }

    complete_apps = ['billing']