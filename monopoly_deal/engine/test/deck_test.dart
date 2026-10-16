import 'package:monopoly_deal_engine/monopoly_deal_engine.dart';
import 'package:test/test.dart';

void main() {
  group('buildFullDeck', () {
    late List<DealCard> deck;

    setUp(() {
      deck = buildFullDeck();
    });

    test('has the documented total card count', () {
      expect(deck.length, totalDeckSize);
      expect(deck.length, 108);
    });

    test('has 20 money cards worth \$57M total', () {
      final money = deck.whereType<MoneyCard>().toList();
      expect(money.length, 20);
      expect(money.fold(0, (sum, c) => sum + c.bankValue), 57);
    });

    test('has 28 single-color property cards, 2-4 per color per set size', () {
      final props = deck.whereType<PropertyCard>().toList();
      expect(props.length, 28);
      for (final color in PropertyColor.values) {
        final count = props.where((p) => p.color == color).length;
        expect(count, propertySetInfo[color]!.setSize,
            reason: '${color.name} should have exactly setSize property cards');
      }
    });

    test('has 11 property wildcards, 2 of them universal', () {
      final wilds = deck.whereType<PropertyWildCard>().toList();
      expect(wilds.length, 11);
      expect(wilds.where((w) => w.isAnyColor).length, 2);
    });

    test('has 13 rent cards, 3 of them wild', () {
      final rents = deck.whereType<RentCard>().toList();
      expect(rents.length, 13);
      expect(rents.where((r) => r.isWild).length, 3);
    });

    test('has 36 action cards matching the documented per-type counts', () {
      final actions = deck.whereType<ActionCard>().toList();
      expect(actions.length, 36);
      const expectedCounts = {
        ActionType.dealBreaker: 2,
        ActionType.justSayNo: 3,
        ActionType.slyDeal: 3,
        ActionType.forcedDeal: 4,
        ActionType.debtCollector: 3,
        ActionType.itsMyBirthday: 3,
        ActionType.passGo: 10,
        ActionType.house: 3,
        ActionType.hotel: 3,
        ActionType.doubleTheRent: 2,
      };
      for (final entry in expectedCounts.entries) {
        final count = actions.where((a) => a.type == entry.key).length;
        expect(count, entry.value, reason: '${entry.key.name} count mismatch');
      }
    });

    test('every card id is unique', () {
      final ids = deck.map((c) => c.id).toSet();
      expect(ids.length, deck.length);
    });
  });
}
