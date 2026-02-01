"""Add mandate_reference and subscription_id to Mandate

Auto-generated for workspace changes.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0009_mandate_add_payment_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="mandate",
            name="mandate_reference",
            field=models.CharField(max_length=128, blank=True, db_index=True, help_text="Provider mandate reference identifier"),
        ),
        migrations.AddField(
            model_name="mandate",
            name="subscription_id",
            field=models.IntegerField(blank=True, null=True, help_text="Provider subscription id if available"),
        ),
    ]
