# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting field 'MapInfo.world_link'
        db.delete_column('map_mapinfo', 'world_link_id')


        # Changing field 'MapInfo.world'
        db.alter_column('map_mapinfo', 'world_id', self.gf('django.db.models.fields.related.ForeignKey')(default=0, to=orm['map.WorldInfo']))
    def backwards(self, orm):
        # Adding field 'MapInfo.world_link'
        db.add_column('map_mapinfo', 'world_link',
                      self.gf('django.db.models.fields.related.ForeignKey')(default=None, related_name='+', null=True, to=orm['map.WorldInfo']),
                      keep_default=False)


        # Changing field 'MapInfo.world'
        db.alter_column('map_mapinfo', 'world_id', self.gf('django.db.models.fields.related.ForeignKey')(null=True, to=orm['map.WorldInfo']))
    models = {
        'map.mapinfo': {
            'Meta': {'object_name': 'MapInfo'},
            'created_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2000, 1, 1, 0, 0)', 'auto_now_add': 'True', 'blank': 'True'}),
            'height': ('django.db.models.fields.IntegerField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'statistics': ('django.db.models.fields.TextField', [], {'default': "'{}'"}),
            'terrain': ('django.db.models.fields.TextField', [], {'default': "'[]'"}),
            'turn_number': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'}),
            'width': ('django.db.models.fields.IntegerField', [], {}),
            'world': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'+'", 'to': "orm['map.WorldInfo']"})
        },
        'map.worldinfo': {
            'Meta': {'object_name': 'WorldInfo'},
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'data': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        }
    }

    complete_apps = ['map']