import logging
from datetime import timedelta

import pytz
import requests
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from celery import shared_task
from django.conf import settings

from .models import ScheduledWithdrawal, Wallet, Transaction
from .utils import request_third_party_deposit

logger = logging.getLogger(__name__)

TIMEOUT = 3


@shared_task
def process_scheduled_withdrawals():
    now = timezone.now().astimezone(pytz.timezone('Asia/Tehran'))
    current_minute_start = now.replace(second=0, microsecond=0)
    next_minute_start = current_minute_start + timedelta(minutes=1)

    with transaction.atomic():
        due_withdrawals = ScheduledWithdrawal.objects.select_for_update(
            skip_locked=True
        ).filter(
            status=ScheduledWithdrawal.PENDING,
            scheduled_for__gte=current_minute_start,
            scheduled_for__lte=next_minute_start
        )

        withdrawal_ids = list(due_withdrawals.values_list('id', flat=True))

        if not withdrawal_ids:
            logger.debug("No due withdrawals to process")
            return

        due_withdrawals.update(status=ScheduledWithdrawal.PROCESSING)
        logger.info(f"Processing {len(withdrawal_ids)} due withdrawals")

    for wid in withdrawal_ids:
        process_single_withdrawal(wid)


def process_single_withdrawal(withdrawal_id):
    withdrawal = ScheduledWithdrawal.objects.filter(
        id=withdrawal_id,
        status=ScheduledWithdrawal.PROCESSING
    ).select_related('wallet').first()

    if not withdrawal:
        logger.warning(f"Withdrawal {withdrawal_id} not found or not in PROCESSING state")
        return

    logger.info(f"Processing withdrawal {withdrawal_id}: {withdrawal.amount} from wallet {withdrawal.wallet.uuid}")

    with transaction.atomic():
        updated = Wallet.objects.filter(
            id=withdrawal.wallet_id,
            balance__gte=withdrawal.amount,
        ).update(
            balance=F('balance') - withdrawal.amount,
        )

        if updated == 0:
            withdrawal.status = ScheduledWithdrawal.FAILED
            withdrawal.error_message = 'Insufficient balance at execution time'
            withdrawal.save()
            logger.warning(
                f"Withdrawal {withdrawal_id} failed: Insufficient balance at execution time "
                f"for wallet {withdrawal.wallet.uuid}"
            )
            return

    bank_success = False
    error_message = None

    try:
        response = request_third_party_deposit()
        bank_success = response.get('data') == 'success'

        if not bank_success:
            error_message = f'Bank rejected the request. Response: {response}'

    except Exception as e:
        error_message = f'Unexpected error: {str(e)} - withdrawal amount refunded'

    if bank_success:
        with transaction.atomic():
            tx = Transaction.objects.create(
                wallet=withdrawal.wallet,
                amount=withdrawal.amount,
                type=Transaction.WITHDRAW
            )
            withdrawal.status = ScheduledWithdrawal.COMPLETED
            withdrawal.transaction = tx
            withdrawal.save()
        logger.info(
            f"Withdrawal {withdrawal_id} completed successfully: {withdrawal.amount} "
            f"from wallet {withdrawal.wallet.uuid}"
        )
    else:

        with transaction.atomic():

            Wallet.objects.filter(id=withdrawal.wallet_id).update(
                balance=F('balance') + withdrawal.amount
            )

            withdrawal.status = ScheduledWithdrawal.FAILED
            withdrawal.error_message = error_message
            withdrawal.save()

        logger.error(
            f"Withdrawal {withdrawal_id} failed: {error_message}. "
            f"Amount refunded to wallet {withdrawal.wallet.uuid}"
        )
