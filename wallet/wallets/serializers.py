from rest_framework import serializers

from wallets.models import Wallet


class WalletSerializer(serializers.ModelSerializer):
    available_balance = serializers.ReadOnlyField()

    class Meta:
        model = Wallet
        fields = ("uuid", "balance", "freeze_amount", "available_balance")
        read_only_fields = ("uuid", "balance", "freeze_amount", "available_balance")
