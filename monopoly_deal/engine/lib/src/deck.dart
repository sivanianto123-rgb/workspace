import 'cards.dart';

/// Builds one full, freshly-shuffled-order-agnostic Monopoly Deal deck.
/// Shuffling is the caller's job (see `Random`-based shuffle in the engine);
/// this just produces the fixed multiset of 106 cards in canonical order.
List<DealCard> buildFullDeck() {
  var nextId = 0;
  String id(String prefix) => '$prefix${nextId++}';

  final cards = <DealCard>[];

  // ---- Money cards (20 cards, $57M total) ----
  const moneyCounts = {10: 1, 5: 2, 4: 3, 3: 3, 2: 5, 1: 6};
  moneyCounts.forEach((value, count) {
    for (var i = 0; i < count; i++) {
      cards.add(MoneyCard(id: id('money-\$${value}M-'), bankValue: value));
    }
  });

  // ---- Property cards (28 cards) ----
  void addProperties(PropertyColor color, int price, List<String> names) {
    for (final name in names) {
      cards.add(PropertyCard(id: id('prop-${color.name}-'), bankValue: price, name: name, color: color));
    }
  }

  addProperties(PropertyColor.brown, 1, ['Mediterranean Avenue', 'Baltic Avenue']);
  addProperties(PropertyColor.lightBlue, 1, ['Oriental Avenue', 'Vermont Avenue', 'Connecticut Avenue']);
  addProperties(PropertyColor.pink, 2, ['St. Charles Place', 'Virginia Avenue', 'States Avenue']);
  addProperties(PropertyColor.orange, 2, ['St. James Place', 'Tennessee Avenue', 'New York Avenue']);
  addProperties(PropertyColor.red, 3, ['Kentucky Avenue', 'Indiana Avenue', 'Illinois Avenue']);
  addProperties(PropertyColor.yellow, 3, ['Atlantic Avenue', 'Ventnor Avenue', 'Marvin Gardens']);
  addProperties(PropertyColor.green, 4, ['Pacific Avenue', 'North Carolina Avenue', 'Pennsylvania Avenue']);
  addProperties(PropertyColor.darkBlue, 4, ['Park Place', 'Boardwalk']);
  addProperties(PropertyColor.railroad, 2, ['Reading Railroad', 'Pennsylvania Railroad', 'B. & O. Railroad', 'Short Line']);
  addProperties(PropertyColor.utility, 2, ['Electric Company', 'Water Works']);

  // ---- Property wildcards (11 cards) ----
  void addWild(int price, int count, Set<PropertyColor> colors) {
    for (var i = 0; i < count; i++) {
      cards.add(PropertyWildCard(id: id('wild-'), bankValue: price, eligibleColors: colors));
    }
  }

  addWild(1, 1, {PropertyColor.lightBlue, PropertyColor.brown});
  addWild(2, 2, {PropertyColor.pink, PropertyColor.orange});
  addWild(3, 2, {PropertyColor.red, PropertyColor.yellow});
  addWild(4, 1, {PropertyColor.darkBlue, PropertyColor.green});
  addWild(4, 1, {PropertyColor.railroad, PropertyColor.green});
  addWild(4, 1, {PropertyColor.railroad, PropertyColor.lightBlue});
  addWild(2, 1, {PropertyColor.utility, PropertyColor.railroad});
  addWild(0, 2, PropertyColor.values.toSet()); // universal "any color" wild

  // ---- Rent cards (13 cards) ----
  void addRent(int price, int count, Set<PropertyColor> colors) {
    for (var i = 0; i < count; i++) {
      cards.add(RentCard(id: id('rent-'), bankValue: price, colors: colors));
    }
  }

  addRent(1, 2, {PropertyColor.brown, PropertyColor.lightBlue});
  addRent(1, 2, {PropertyColor.pink, PropertyColor.orange});
  addRent(1, 2, {PropertyColor.red, PropertyColor.yellow});
  addRent(1, 2, {PropertyColor.green, PropertyColor.darkBlue});
  addRent(1, 2, {PropertyColor.railroad, PropertyColor.utility});
  addRent(3, 3, PropertyColor.values.toSet()); // wild rent

  // ---- Action cards (36 cards) ----
  void addAction(ActionType type, int price, int count) {
    for (var i = 0; i < count; i++) {
      cards.add(ActionCard(id: id('action-${type.name}-'), bankValue: price, type: type));
    }
  }

  addAction(ActionType.passGo, 1, 10);
  addAction(ActionType.itsMyBirthday, 2, 3);
  addAction(ActionType.debtCollector, 3, 3);
  addAction(ActionType.slyDeal, 3, 3);
  addAction(ActionType.forcedDeal, 3, 4);
  addAction(ActionType.house, 3, 3);
  addAction(ActionType.doubleTheRent, 1, 2);
  addAction(ActionType.dealBreaker, 5, 2);
  addAction(ActionType.justSayNo, 4, 3);
  addAction(ActionType.hotel, 4, 3);

  return cards;
}

/// Deck composition reference, so callers/tests don't have to re-derive
/// these from the builder:
const deckCardCountsByCategory = {
  'money': 20,
  'property': 28,
  'propertyWild': 11,
  'rent': 13,
  'action': 36,
};

final int totalDeckSize = deckCardCountsByCategory.values.reduce((a, b) => a + b);
