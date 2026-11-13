import json
from types import SimpleNamespace

import pytest

from app.services import bank_sync as bank
from app.services.finance import FinanceService
from app.services.habits import get_db_connection

pytestmark = pytest.mark.usefixtures('isolated_lote6_data')


@pytest.fixture
def account(monkeypatch):
    bank.initialize()
    monkeypatch.setattr(bank, '_model', SimpleNamespace(ask=lambda *a, **k: 'Alimentação'))
    return {'id': 'account1', 'name': 'Conta teste'}


def tx(**changes):
    return dict(id='t1', accountId='account1', amount=-25, type='DEBIT', status='POSTED',
                currencyCode='BRL', date='2026-11-13T00:00:00.000Z', description='Mercado', **changes)


def test_import_repeat_update_and_manual_category(account):
    row = tx()
    assert bank.import_snapshot('c1', [account], {'account1': [row]})['added'] == 1
    assert bank.import_snapshot('c1', [account], {'account1': [row]})['changed'] == 0
    entry = FinanceService.list_transactions()[0]
    assert entry['category'] == 'Alimentação'
    FinanceService.update_transaction(entry['id'], 'expense', 25, 'Minha categoria', 'Mercado', '2026-11-13')
    row['amount'] = -30
    bank.import_snapshot('c1', [account], {'account1': [row]})
    assert FinanceService.get_transaction(entry['id'])['category'] == 'Minha categoria'
    assert FinanceService.get_transaction(entry['id'])['amount'] == 30
    assert len(FinanceService.list_transactions()) == 1
    FinanceService.delete_transaction(entry['id'])
    bank.import_snapshot('c1', [account], {'account1': [row]})
    assert not FinanceService.list_transactions()


def test_pending_then_posted_and_shorter_snapshot_preserves_history(account):
    row = tx(); row['status'] = 'PENDING'
    bank.import_snapshot('c1', [account], {'account1': [row]})
    assert not FinanceService.list_transactions()
    row['status'] = 'POSTED'
    bank.import_snapshot('c1', [account], {'account1': [row]})
    assert len(FinanceService.list_transactions()) == 1
    bank.import_snapshot('c1', [account], {'account1': []})
    assert len(FinanceService.list_transactions()) == 1


def test_multiple_accounts_and_failed_validation_is_atomic(account):
    other = {**account, 'id': 'account2'}
    row2 = {**tx(), 'accountId': 'account2'}
    bank.import_snapshot('c1', [account, other], {'account1': [tx()], 'account2': [row2]})
    assert len(FinanceService.list_transactions()) == 2
    row2['amount'] = float('nan')
    with pytest.raises(ValueError):
        bank.import_snapshot('c1', [account, other], {'account1': [], 'account2': [row2]})
    assert len(FinanceService.list_transactions()) == 2


def test_transfer_card_payment_foreign_currency_held(account):
    same = {'documentNumber': {'value': '123.456.789-00'}}
    rows = [tx(paymentData={'payer': same, 'receiver': same}), tx(operationType='PAGAMENTO_FATURA')]
    rows[1]['id'] = 't2'
    rows.append({**tx(), 'id': 't3', 'currencyCode': 'USD'})
    bank.import_snapshot('c1', [account], {'account1': rows})
    assert not FinanceService.list_transactions()
    assert {r['state'] for r in bank.status()['held']} == {'transfer', 'card_payment', 'review_currency_or_type'}


def test_pagination_and_invalid_cursor():
    client = bank.Pluggy.__new__(bank.Pluggy)
    calls = []
    def request(method, path):
        calls.append(path)
        return {'results': [tx()], 'next': '?accountId=a&after=abc'} if len(calls) == 1 else {'results': [], 'next': None}
    client.request = request
    assert len(client.transactions('a')) == 1
    assert calls[-1] == '/v2/transactions?accountId=a&after=abc'
    client.request = lambda *a: {'results': [], 'next': 'https://untrusted.invalid'}
    with pytest.raises(ValueError):
        client.transactions('a')


def test_settings_and_no_secrets(account, monkeypatch):
    monkeypatch.setenv('PLUGGY_CLIENT_SECRET', 'never-visible')
    for minutes in (0, 4, 1441, True, '30'):
        with pytest.raises(ValueError):
            bank.command({'action': 'settings', 'enabled': True, 'minutes': minutes})
    result = bank.command({'action': 'settings', 'enabled': True, 'minutes': 5})
    assert result['enabled'] == 1 and result['minutes'] == 5
    assert 'never-visible' not in json.dumps(result)


def test_sync_does_not_refetch_unchanged_bank_snapshot(account, monkeypatch):
    with get_db_connection() as db:
        db.execute('INSERT INTO bank_connections(id,name,imported_version) VALUES (?,?,?)', ('c1','Bank','version1'))
    calls = []
    class Client:
        def request(self, method, path):
            calls.append((method, path))
            return {'status': 'UPDATED', 'lastUpdatedAt': 'version1'}
    monkeypatch.setattr(bank, 'Pluggy', Client)
    bank.sync()
    assert calls == [('GET', '/items/c1')]
    assert bank.status()['connections'][0]['checked'] > 0


def test_receipt_only_on_committed_change(account, monkeypatch):
    from app.agent import popups
    from app.storage import runtime_settings
    events = []
    monkeypatch.setattr(runtime_settings, 'get_popup_settings', lambda: {'enabled': True, 'ttl_seconds': 10})
    monkeypatch.setattr(popups, 'emit', events.append)
    for _ in range(2):
        bank.import_snapshot('c1', [account], {'account1': [tx()]})
    assert len(events) == 1
    assert events[0]['data']['before'] == 0 and events[0]['data']['after'] == -25
