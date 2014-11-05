from django.db import models

class Schema(models.Model):
	org_id = models.CharField(max_length=255)
	org_name = models.CharField(max_length=255)
	username = models.CharField(max_length=255)
	api_version = models.CharField(max_length=255)

	def sorted_objects(self):
		return self.object_set.order_by('label')

class Object(models.Model):
	schema = models.ForeignKey(Schema)
	label = models.CharField(max_length=255)
	api_name = models.CharField(max_length=255)

	def sorted_fields(self):
		return self.field_set.order_by('label')

class Field(models.Model):
	object = models.ForeignKey(Object)
	label = models.CharField(max_length=255)
	api_name = models.TextField(max_length=255)
	data_type = models.TextField()

class Debug(models.Model):
	debug = models.TextField()
