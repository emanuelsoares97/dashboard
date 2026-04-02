from django.db import migrations


SERVICE_TYPE_LABEL_FIXES = {
    'Voz p\u00f3s-paga': 'Voz p\u00f3s-pago',
    'Voz pr\u00e9-paga': 'Voz pr\u00e9-pago',
    'Voz p\u00c3\u00b3s-paga': 'Voz p\u00f3s-pago',
    'Voz pr\u00c3\u00a9-paga': 'Voz pr\u00e9-pago',
}


def normalize_service_type_labels(apps, schema_editor):
    ServiceType = apps.get_model('inbound', 'ServiceType')

    for old_label, new_label in SERVICE_TYPE_LABEL_FIXES.items():
        ServiceType.objects.filter(label=old_label).update(label=new_label)


def noop_reverse(apps, schema_editor):
    # Data cleanup migration: reverse is intentionally a no-op.
    return


class Migration(migrations.Migration):

    dependencies = [
        ('inbound', '0003_delete_callrecord_and_more'),
    ]

    operations = [
        migrations.RunPython(normalize_service_type_labels, reverse_code=noop_reverse),
    ]
