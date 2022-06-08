from pytezos import pytezos

class Bot:
  def __init__(self, shell, key):
    self.pytezos_cli = pytezos.using(shell=shell, key=key)
    self.last_now = self.pytezos_cli.now()
