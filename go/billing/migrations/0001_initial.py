# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    depends_on = (
        ("auth", "0001_initial"),
    )

    def forwards(self, orm):
        
        # Adding model 'TagPool'
        db.create_table('billing_tagpool', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=100)),
            ('description', self.gf('django.db.models.fields.TextField')(blank=True)),
        ))
        db.send_create_signal('billing', ['TagPool'])

        # Adding model 'Account'
        db.create_table('billing_account', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('account_number', self.gf('django.db.models.fields.CharField')(unique=True, max_length=100)),
            ('description', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('credit_balance', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('alert_threshold', self.gf('django.db.models.fields.DecimalField')(default=0.0, max_digits=10, decimal_places=2)),
            ('alert_credit_balance', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal('billing', ['Account'])

        # Adding model 'MessageCost'
        db.create_table('billing_messagecost', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('account', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['billing.Account'], null=True, blank=True)),
            ('tag_pool', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['billing.TagPool'])),
            ('message_direction', self.gf('django.db.models.fields.CharField')(max_length=20)),
            ('message_cost', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('markup_percent', self.gf('django.db.models.fields.DecimalField')(default=0.0, max_digits=10, decimal_places=2)),
        ))
        db.send_create_signal('billing', ['MessageCost'])

        # Adding model 'Transaction'
        db.create_table('billing_transaction', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('account_number', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('tag_pool_name', self.gf('django.db.models.fields.CharField')(max_length=100, blank=True)),
            ('message_direction', self.gf('django.db.models.fields.CharField')(max_length=20, blank=True)),
            ('message_cost', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('markup_percent', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=10, decimal_places=2, blank=True)),
            ('credit_factor', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=10, decimal_places=2, blank=True)),
            ('credit_amount', self.gf('django.db.models.fields.IntegerField')()),
            ('status', self.gf('django.db.models.fields.CharField')(default='Pending', max_length=20)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('last_modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
        ))
        db.send_create_signal('billing', ['Transaction'])


    def backwards(self, orm):
        
        # Deleting model 'TagPool'
        db.delete_table('billing_tagpool')

        # Deleting model 'Account'
        db.delete_table('billing_account')

        # Deleting model 'MessageCost'
        db.delete_table('billing_messagecost')

        # Deleting model 'Transaction'
        db.delete_table('billing_transaction')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2013, 9, 25, 8, 58, 37, 911472)'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2013, 9, 25, 8, 58, 37, 911410)'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'billing.account': {
            'Meta': {'object_name': 'Account'},
            'account_number': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'}),
            'alert_credit_balance': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'alert_threshold': ('django.db.models.fields.DecimalField', [], {'default': '0.0', 'max_digits': '10', 'decimal_places': '2'}),
            'credit_balance': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'billing.messagecost': {
            'Meta': {'object_name': 'MessageCost'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['billing.Account']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'markup_percent': ('django.db.models.fields.DecimalField', [], {'default': '0.0', 'max_digits': '10', 'decimal_places': '2'}),
            'message_cost': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'message_direction': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'tag_pool': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['billing.TagPool']"})
        },
        'billing.tagpool': {
            'Meta': {'object_name': 'TagPool'},
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'})
        },
        'billing.transaction': {
            'Meta': {'object_name': 'Transaction'},
            'account_number': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'credit_amount': ('django.db.models.fields.IntegerField', [], {}),
            'credit_factor': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '10', 'decimal_places': '2', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'markup_percent': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '10', 'decimal_places': '2', 'blank': 'True'}),
            'message_cost': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'message_direction': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'Pending'", 'max_length': '20'}),
            'tag_pool_name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        }
    }

    complete_apps = ['billing']
