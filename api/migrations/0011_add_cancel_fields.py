from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0010_mandate_reference_subscription"),
    ]

    operations = [
        migrations.AddField(
            model_name="mandate",
            name="cancel_response",
            field=models.JSONField(null=True, blank=True, help_text="Raw provider response for cancel attempts"),
        ),
        migrations.AddField(
            model_name="mandate",
            name="cancelled_at",
            field=models.DateTimeField(null=True, blank=True, help_text="When the mandate was cancelled by the user/provider"),
        ),
    ]
