from rest_framework.generics import CreateAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from wallets.models import Wallet
from wallets.serializers import WalletSerializer
from wallets.services import deposit_to_wallet, schedule_withdrawal_service

class CreateWalletView(CreateAPIView):
    serializer_class = WalletSerializer


class RetrieveWalletView(RetrieveAPIView):
    serializer_class = WalletSerializer
    queryset = Wallet.objects.all()
    lookup_field = "uuid"


class CreateDepositView(APIView):
    def post(self, request, *args, **kwargs):
        wallet_uuid = kwargs.get('uuid')
        amount = request.data.get('amount', 0)
        try:
            txn = deposit_to_wallet(wallet_uuid, amount)

            return Response({
                'wallet_uuid': str(txn.wallet.uuid),
                'amount': txn.amount,
                'new_balance': txn.wallet.balance
            }, status=201)

        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        except Wallet.DoesNotExist:
            return Response({'error': 'wallet not found'}, status=404)


class ScheduleWithdrawView(APIView):
    def post(self, request, *args, **kwargs):
        wallet_uuid = kwargs.get('uuid')
        amount = request.data.get('amount', 0)
        scheduled_time = request.data.get('scheduled_for')

        try:
            response_data = schedule_withdrawal_service(wallet_uuid, amount, scheduled_time)
            return Response(response_data, status=201)

        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        except Wallet.DoesNotExist:
            return Response({'error': 'wallet not found'}, status=404)