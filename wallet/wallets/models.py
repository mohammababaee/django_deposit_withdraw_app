import uuid

from utils.models import BaseModel
from django.db import models
from django.core.exceptions import ValidationError


class Wallet(BaseModel):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    balance = models.PositiveBigIntegerField(default=0)
    freeze_amount = models.PositiveBigIntegerField(default=0)

    @property
    def available_balance(self):
        """Money that can actually be used (not frozen for pending withdrawals)"""
        return self.balance - self.freeze_amount


class Transaction(BaseModel):
    DEPOSIT = 'deposit'
    WITHDRAW = 'withdraw'
    TYPE_CHOICES = [(DEPOSIT, 'Deposit'), (WITHDRAW, 'Withdraw')]

    amount = models.PositiveBigIntegerField()
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name='transactions')

    class Meta:
        indexes = [
            models.Index(fields=['wallet', '-created_at']),
            models.Index(fields=['type', '-created_at']),
        ]


class ScheduledWithdrawal(BaseModel):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (PROCESSING, 'Processing'),
        (COMPLETED, 'Completed'),
        (FAILED, 'Failed')
    ]

    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name='scheduled_withdrawals')
    amount = models.PositiveBigIntegerField()
    scheduled_for = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    transaction = models.ForeignKey(Transaction, null=True, blank=True, on_delete=models.SET_NULL)
    error_message = models.TextField(null=True, blank=True)
    is_valid = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'scheduled_for']),
            models.Index(fields=['wallet', 'status']),
        ]
