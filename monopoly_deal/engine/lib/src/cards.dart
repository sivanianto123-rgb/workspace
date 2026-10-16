/// Card data model for Monopoly Deal.
///
/// Values are sourced from the official rules
/// (https://monopolydealrules.com/index.php?page=play), cross-checked
/// against the photographed card counts/denominations there. The eight
/// Red/Yellow/Utility property cards use the standard published
/// prices/rents (that page's screenshot cut off before showing them) but
/// follow the same pattern as every other confirmed color.
library;

/// The ten property colors (railroad and utility count as "colors" for set
/// purposes, same as the physical cards).
enum PropertyColor {
  brown,
  lightBlue,
  pink,
  orange,
  red,
  yellow,
  green,
  darkBlue,
  railroad,
  utility,
}

/// Per-color set size and rent table (rent by number of cards owned in that
/// color, 1-indexed; the last entry is the "full set" rent).
class PropertySetInfo {
  final int setSize;
  final List<int> rentByCountOwned;

  const PropertySetInfo({required this.setSize, required this.rentByCountOwned});

  int rentFor(int countOwned) {
    if (countOwned <= 0) return 0;
    final idx = countOwned.clamp(1, setSize) - 1;
    return rentByCountOwned[idx];
  }
}

const Map<PropertyColor, PropertySetInfo> propertySetInfo = {
  PropertyColor.brown: PropertySetInfo(setSize: 2, rentByCountOwned: [1, 2]),
  PropertyColor.darkBlue: PropertySetInfo(setSize: 2, rentByCountOwned: [3, 8]),
  PropertyColor.green: PropertySetInfo(setSize: 3, rentByCountOwned: [2, 4, 7]),
  PropertyColor.lightBlue: PropertySetInfo(setSize: 3, rentByCountOwned: [1, 2, 3]),
  PropertyColor.orange: PropertySetInfo(setSize: 3, rentByCountOwned: [1, 3, 5]),
  PropertyColor.pink: PropertySetInfo(setSize: 3, rentByCountOwned: [1, 2, 4]),
  PropertyColor.railroad: PropertySetInfo(setSize: 4, rentByCountOwned: [1, 2, 3, 4]),
  PropertyColor.red: PropertySetInfo(setSize: 3, rentByCountOwned: [2, 3, 6]),
  PropertyColor.yellow: PropertySetInfo(setSize: 3, rentByCountOwned: [2, 4, 6]),
  PropertyColor.utility: PropertySetInfo(setSize: 2, rentByCountOwned: [1, 2]),
};

/// Base type for every physical card in the deck. [id] is a unique instance
/// identifier (two $1M bills are different cards with the same [bankValue]).
sealed class DealCard {
  final String id;

  /// Value in millions ($M) when banked or used to pay rent/fees.
  final int bankValue;

  const DealCard({required this.id, required this.bankValue});
}

final class MoneyCard extends DealCard {
  const MoneyCard({required super.id, required super.bankValue});

  @override
  String toString() => 'Money(\$${bankValue}M)';
}

final class PropertyCard extends DealCard {
  final String name;
  final PropertyColor color;

  const PropertyCard({
    required super.id,
    required super.bankValue,
    required this.name,
    required this.color,
  });

  @override
  String toString() => 'Property($name, ${color.name})';
}

/// A two-color (or, for the two universal cards, any-color) wildcard
/// property. When placed into play it is assigned to exactly one color
/// from [eligibleColors] (chosen by the player at play time, and
/// re-assignable later as long as it isn't part of a complete set).
final class PropertyWildCard extends DealCard {
  final Set<PropertyColor> eligibleColors;

  const PropertyWildCard({
    required super.id,
    required super.bankValue,
    required this.eligibleColors,
  });

  bool get isAnyColor => eligibleColors.length == PropertyColor.values.length;

  @override
  String toString() => 'Wild(${isAnyColor ? "any color" : eligibleColors.map((c) => c.name).join("/")})';
}

/// A rent card. [colors] holds the (one or two) colors it can charge rent
/// for; a "wild" rent card is eligible for every color (player picks one
/// color they own when playing it).
final class RentCard extends DealCard {
  final Set<PropertyColor> colors;

  const RentCard({
    required super.id,
    required super.bankValue,
    required this.colors,
  });

  bool get isWild => colors.length == PropertyColor.values.length;

  @override
  String toString() => 'Rent(${isWild ? "any color" : colors.map((c) => c.name).join("/")})';
}

enum ActionType {
  dealBreaker,
  justSayNo,
  slyDeal,
  forcedDeal,
  debtCollector,
  itsMyBirthday,
  passGo,
  house,
  hotel,
  doubleTheRent,
}

final class ActionCard extends DealCard {
  final ActionType type;

  const ActionCard({
    required super.id,
    required super.bankValue,
    required this.type,
  });

  @override
  String toString() => 'Action(${type.name})';
}
