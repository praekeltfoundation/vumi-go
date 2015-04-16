# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models
from django.db.utils import DatabaseError


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Removing unique constraint on 'MessageCost', fields ['account', 'tag_pool', 'message_direction']
        db.delete_unique(u'billing_messagecost', ['account_id', 'tag_pool_id', 'message_direction'])

        # Adding unique constraint on 'MessageCost', fields ['account', 'tag_pool', 'message_direction', 'provider']
        db.create_unique(u'billing_messagecost', ['account_id', 'tag_pool_id', 'message_direction', 'provider'])

        try:
            # Removing index on 'MessageCost', fields ['account', 'tag_pool', 'message_direction']
            db.delete_index(u'billing_messagecost', ['account_id', 'tag_pool_id', 'message_direction'])
        except DatabaseError as e:
            if not str(e).startswith("no such index: billing_messagecost_account_id_"):
                raise

        # Adding index on 'MessageCost', fields ['account', 'tag_pool', 'message_direction', 'provider']
        db.create_index(u'billing_messagecost', ['account_id', 'tag_pool_id', 'message_direction', 'provider'])


    def backwards(self, orm):
        try:
            # Removing index on 'MessageCost', fields ['account', 'tag_pool', 'message_direction', 'provider']
            db.delete_index(u'billing_messagecost', ['account_id', 'tag_pool_id', 'message_direction', 'provider'])
        except DatabaseError as e:
            if not str(e).startswith("no such index: billing_messagecost_account_id_"):
                raise

        # Adding index on 'MessageCost', fields ['account', 'tag_pool', 'message_direction']
        db.create_index(u'billing_messagecost', ['account_id', 'tag_pool_id', 'message_direction'])

        # Removing unique constraint on 'MessageCost', fields ['account', 'tag_pool', 'message_direction', 'provider']
        db.delete_unique(u'billing_messagecost', ['account_id', 'tag_pool_id', 'message_direction', 'provider'])

        # Adding unique constraint on 'MessageCost', fields ['account', 'tag_pool', 'message_direction']
        db.create_unique(u'billing_messagecost', ['account_id', 'tag_pool_id', 'message_direction'])


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
            'credit_balance': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '20', 'decimal_places': '6'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_topup_balance': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '20', 'decimal_places': '6'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['base.GoUser']"})
        },
        u'billing.lineitem': {
            'Meta': {'object_name': 'LineItem'},
            'billed_by': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'channel': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'channel_type': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '20', 'decimal_places': '6'}),
            'credits': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'null': 'True', 'max_digits': '20', 'decimal_places': '6'}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'statement': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['billing.Statement']"}),
            'unit_cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '20', 'decimal_places': '6'}),
            'units': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'billing.lowcreditnotification': {
            'Meta': {'object_name': 'LowCreditNotification'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['billing.Account']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'credit_balance': ('django.db.models.fields.DecimalField', [], {'max_digits': '20', 'decimal_places': '6'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'success': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'threshold': ('django.db.models.fields.DecimalField', [], {'max_digits': '10', 'decimal_places': '2'})
        },
        u'billing.messagecost': {
            'Meta': {'unique_together': "[['account', 'tag_pool', 'message_direction', 'provider']]", 'object_name': 'MessageCost', 'index_together': "[['account', 'tag_pool', 'message_direction', 'provider']]"},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['billing.Account']", 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'markup_percent': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '10', 'decimal_places': '2'}),
            'message_cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '10', 'decimal_places': '3'}),
            'message_direction': ('django.db.models.fields.CharField', [], {'max_length': '20', 'db_index': 'True'}),
            'provider': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'session_cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '10', 'decimal_places': '3'}),
            'session_unit_cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '10', 'decimal_places': '3'}),
            'session_unit_time': ('django.db.models.fields.DecimalField', [], {'default': "'20.0'", 'max_digits': '10', 'decimal_places': '3'}),
            'storage_cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'max_digits': '10', 'decimal_places': '3'}),
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
            'message_credits': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'null': 'True', 'max_digits': '20', 'decimal_places': '6'}),
            'message_direction': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'message_id': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'provider': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'session_cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'null': 'True', 'max_digits': '10', 'decimal_places': '3'}),
            'session_created': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'session_credits': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'null': 'True', 'max_digits': '20', 'decimal_places': '6'}),
            'session_length': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'null': 'True', 'max_digits': '10', 'decimal_places': '3'}),
            'session_length_cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'null': 'True', 'max_digits': '10', 'decimal_places': '3'}),
            'session_length_credits': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'null': 'True', 'max_digits': '20', 'decimal_places': '6'}),
            'session_unit_cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'null': 'True', 'max_digits': '10', 'decimal_places': '3'}),
            'session_unit_time': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'null': 'True', 'max_digits': '10', 'decimal_places': '3'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'Pending'", 'max_length': '20'}),
            'storage_cost': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'null': 'True', 'max_digits': '10', 'decimal_places': '3'}),
            'storage_credits': ('django.db.models.fields.DecimalField', [], {'default': "'0.0'", 'null': 'True', 'max_digits': '20', 'decimal_places': '6'}),
            'tag_name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'tag_pool_name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'transaction_type': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'})
        },
        u'billing.transactionarchive': {
            'Meta': {'object_name': 'TransactionArchive'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['billing.Account']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'filename': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'from_date': ('django.db.models.fields.DateField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'archive_created'", 'max_length': '32'}),
            'to_date': ('django.db.models.fields.DateField', [], {})
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
