from bot import Bot


class FA1TokenBot(Bot):
    def __init__(self, operator_contract, token_contract_address, shell, key, token_decimals=18):
        super().__init__(shell, key)
        self.token_contract = self.pytezos_cli.contract(token_contract_address)
        self.token_id = 0
        self.operator_contract = operator_contract
        self.token_decimals = token_decimals

    def add_operator(self):
        return self.approve(10**6*10**self.token_decimals)

    def approve(self, amount):
        try:
            approved_amount = self.token_contract.getAllowance((self.pytezos_cli.key.public_key_hash(), self.operator_contract, None)).callback_view()
        except:
            try:
                approved_amount = self.token_contract.getAllowance(request=(self.pytezos_cli.key.public_key_hash(), self.operator_contract), callback=None).callback_view()
            except:
                approved_amount = 0
        print(approved_amount)
        if approved_amount < amount*10**self.token_decimals:
            return [
                self.token_contract.approve((self.operator_contract, 0)),
                self.token_contract.approve((self.operator_contract, int(amount*10**self.token_decimals)))
            ]
        else:
            return []

    def get_balance(self):
        return self.token_contract.getBalance((self.pytezos_cli.key.public_key_hash(), None)).callback_view()/10**self.token_decimals         