# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting field 'LineItem.total_cost'
        db.delete_column(u'billing_lineitem', 'total_cost')

        # Deleting field 'LineItem.message_direction'
        db.delete_column(u'billing_lineitem', 'message_direction')

        # Deleting field 'LineItem.tag_pool_name'
        db.delete_column(u'billing_lineitem', 'tag_pool_name')

        # Deleting field 'LineItem.tag_name'
        db.delete_column(u'billing_lineitem', 'tag_name')

        # Adding field 'LineItem.billed_by'
        db.add_column(u'billing_lineitem', 'billed_by',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=100, blank=True),
                      keep_default=False)

        # Adding field 'LineItem.channel'
        db.add_column(u'billing_lineitem', 'channel',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=100, null=True, blank=True),
                      keep_default=False)

        # Adding field 'LineItem.channel_type'
        db.add_column(u'billing_lineitem', 'channel_type',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=100, null=True, blank=True),
                      keep_default=False)

        # Adding field 'LineItem.description'
        db.add_column(u'billing_lineitem', 'description',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=100, blank=True),
                      keep_default=False)

        # Adding field 'LineItem.units'
        db.add_column(u'billing_lineitem', 'units',
                      self.gf('django.db.models.fields.IntegerField')(default=0),
                      keep_default=False)

        # Adding field 'LineItem.credits'
        db.add_column(u'billing_lineitem', 'credits',
                      self.gf('django.db.models.fields.IntegerField')(default=0),
                      keep_default=False)

        # Adding field 'LineItem.unit_cost'
        db.add_column(u'billing_lineitem', 'unit_cost',
                      self.gf('django.db.models.fields.DecimalField')(default='0.0', max_digits=20, decimal_places=6),
                      keep_default=False)

        # Adding field 'LineItem.cost'
        db.add_column(u'billing_lineitem', 'cost',
                      self.gf('django.db.models.fields.DecimalField')(default='0.0', max_digits=20, decimal_places=6),
                      keep_default=False)


    def backwards(self, orm):
        # Adding field 'LineItem.total_cost'
        db.add_column(u'billing_lineitem', 'total_cost',
                      self.gf('django.db.models.fields.IntegerField')(default=0),
                      keep_default=False)

        # Adding field 'LineItem.message_direction'
        db.add_column(u'billing_lineitem', 'message_direction',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=20, blank=True),
                      keep_default=False)

        # Adding field 'LineItem.tag_pool_name'
        db.add_column(u'billing_lineitem', 'tag_pool_name',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=100, blank=True),
                      keep_default=False)

        # Adding field 'LineItem.tag_name'
        db.add_column(u'billing_lineitem', 'tag_name',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=100, blank=True),
                      keep_default=False)

        # Deleting field 'LineItem.billed_by'
        db.delete_column(u'billing_lineitem', 'billed_by')

        # Deleting field 'LineItem.channel'
        db.delete_column(u'billing_lineitem', 'channel')

        # Deleting field 'LineItem.channel_type'
        db.delete_column(u'billing_lineitem', 'channel_type')

        # Deleting field 'LineItem.description'
        db.delete_column(u'billing_lineitem', 'description')

        # Deleting field 'LineItem.units'
        db.delete_column(u'billing_lineitem', 'units')

        # Deleting field 'LineItem.credits'
        db.delete_column(u'billing_lineitem', 'credits')

        # Deleting field 'LineItem.unit_cost'
        db.delete_column(u'billing_lineitem', 'unit_cost')

        # Deleting field 'LineItem.cost'
        db.delete_column(u'billing_lineitem', 'cost')


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
            'alert_credit_balance': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '20', 'decimal_places': '6'}),
            'alert_threshold': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '10', 'decimal_places': '2'}),
            'credit_balance': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '20', 'decimal_places': '6'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['base.GoUser']"})
        },
        u'billing.lineitem': {
            'Meta': {'object_name': 'LineItem'},
            'billed_by': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100', 'blank': 'True'}),
            'channel': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'channel_type': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '20', 'decimal_places': '6'}),
            'credits': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'description': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'statement': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['billing.Statement']"}),
            'unit_cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '20', 'decimal_places': '6'}),
            'units': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'billing.messagecost': {
            'Meta': {'unique_together': "[['account', 'tag_pool', 'message_direction']]", 'object_name': 'MessageCost', 'index_together': "[['account', 'tag_pool', 'message_direction']]"},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['billing.Account']", 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'markup_percent': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '10', 'decimal_places': '2'}),
            'message_cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '10', 'decimal_places': '3'}),
            'message_direction': ('django.db.models.fields.CharField', [], {'max_length': '20', 'db_index': 'True'}),
            'session_cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '10', 'decimal_places': '3'}),
            'tag_pool': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['billing.TagPool']", 'null': 'True', 'blank': 'True'})
        },
        u'billing.statement': {
            'Meta': {'object_name': 'Statement'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['billing.Account']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'from_date': ('django.db.models.fields.DateField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'to_date': ('django.db.models.fields.DateField', [], {}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '40'})
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
            'credit_amount': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '20', 'decimal_places': '6'}),
            'credit_factor': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '10', 'decimal_places': '2', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'markup_percent': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '10', 'decimal_places': '2', 'blank': 'True'}),
            'message_cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'null': 'True', 'max_digits': '10', 'decimal_places': '3'}),
            'message_direction': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'message_id': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'session_cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'null': 'True', 'max_digits': '10', 'decimal_places': '3'}),
            'session_created': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
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