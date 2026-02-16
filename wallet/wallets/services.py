import logging
import pytz
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from datetime import datetime

from wallets.models import Transaction, Wallet, ScheduledWithdrawal

logger = logging.getLogger(__name__)

IRAN_TZ = pytz.timezone('Asia/Tehran')

@transaction.atomic
def deposit_to_wallet(wallet_uuid: str, amount: int) -> Transaction:
    if amount <= 0:
        logger.warning(f"Deposit attempt with invalid amount: {amount} for wallet {wallet_uuid}")
        raise ValueError("Amount must be positive")

    wallet = Wallet.objects.select_for_update().get(uuid=wallet_uuid)
    wallet.balance += amount
    wallet.save()

    txn = Transaction.objects.create(
        wallet=wallet,
        amount=amount,
        type=Transaction.DEPOSIT
    )
    logger.info(f"Deposit successful: {amount} to wallet {wallet_uuid}. New balance: {wallet.balance}")
    return txn


@transaction.atomic
def create_withdraw_request(wallet_uuid: str, amount: int, scheduled_for: datetime) -> ScheduledWithdrawal:
    if amount <= 0:
        logger.warning(f"Withdrawal attempt with invalid amount: {amount} for wallet {wallet_uuid}")
        raise ValueError("Amount must be positive")

    if scheduled_for <= timezone.now():
        logger.warning(f"Withdrawal attempt with past time: {scheduled_for} for wallet {wallet_uuid}")
        raise ValueError("Scheduled time must be in the future")

    wallet = Wallet.objects.get(uuid=wallet_uuid)

    withdraw_request = ScheduledWithdrawal.objects.create(
        wallet=wallet,
        amount=amount,
        scheduled_for=scheduled_for,
        status=ScheduledWithdrawal.PENDING,
    )

    logger.info(
        f"Withdrawal scheduled: {amount} from wallet {wallet_uuid} at {scheduled_for}. "
        f"New frozen amount: {wallet.freeze_amount + amount}"
    )
    return withdraw_request


def schedule_withdrawal_service(wallet_uuid: str, amount: int, scheduled_time_str: str) -> dict:

    if not scheduled_time_str:
        raise ValueError('time is required (format: HH:MM:SS or HH:MM)')

    try:
        scheduled_datetime = datetime.strptime(scheduled_time_str, '%Y-%m-%d %H:%M:%S')
        scheduled_datetime = timezone.make_aware(scheduled_datetime, timezone=IRAN_TZ)
    except ValueError:
        raise ValueError('Invalid datetime format. Use YYYY-MM-DD HH:MM:SS')

    if scheduled_datetime < timezone.now():
        raise ValueError('Scheduled time cannot be in the past')

    withdrawal = create_withdraw_request(wallet_uuid, amount, scheduled_datetime)

    return {
        'wallet_uuid': str(withdrawal.wallet.uuid),
        'amount': withdrawal.amount,
        'scheduled_for': withdrawal.scheduled_for.strftime('%Y-%m-%d %H:%M:%S'),
        'status': withdrawal.status
    }
