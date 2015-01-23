from django.contrib import admin
from getschema.models import Schema, Object, Field, Debug

class FieldInline(admin.TabularInline):
	fields = ['label','api_name','data_type']
	ordering = ['label']
	model = Field
	extra = 0

class ObjectInline(admin.TabularInline):
	fields = ['label','api_name']
	ordering = ['label']
	model = Object
	extra = 0

class SchemaAdmin(admin.ModelAdmin):
	list_display = ('org_id','api_version', 'created_date','finished_date','status')
	inlines = [ObjectInline]

class ObjectAdmin(admin.ModelAdmin):
	list_display = ('label','api_name')
	inlines = [FieldInline]

class DebugAdmin(admin.ModelAdmin):
	pass

admin.site.register(Schema, SchemaAdmin)
admin.site.register(Debug, DebugAdmin)