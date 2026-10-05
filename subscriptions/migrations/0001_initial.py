import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('vacancies', '0010_seed_skill_stop_phrases'),
    ]

    operations = [
        migrations.CreateModel(
            name='Subscriber',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chat_id', models.BigIntegerField(unique=True)),
                ('username', models.CharField(blank=True, max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ('-created_at',),
                'permissions': (('access_bot_api', 'Can manage subscribers through the bot API'),),
            },
        ),
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('remote_only', models.BooleanField(default=False)),
                ('min_salary_usd', models.PositiveIntegerField(blank=True, null=True)),
                ('max_experience_years', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('skills', models.ManyToManyField(blank=True, related_name='subscriptions', to='vacancies.skill')),
                ('subscriber', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subscriptions', to='subscriptions.subscriber')),
            ],
            options={
                'ordering': ('created_at',),
            },
        ),
        migrations.CreateModel(
            name='Delivery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('delivered_at', models.DateTimeField(auto_now_add=True)),
                ('vacancy', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deliveries', to='vacancies.vacancy')),
                ('subscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deliveries', to='subscriptions.subscription')),
            ],
            options={
                'verbose_name_plural': 'deliveries',
                'constraints': [models.UniqueConstraint(fields=('subscription', 'vacancy'), name='delivery_unique_per_subscription')],
            },
        ),
    ]
