import 'dart:math' show Random;

import 'cards.dart';

export 'dart:math' show Random;

/// A color-group of properties a player has placed in front of them.
/// [cards] holds [PropertyCard]s and/or [PropertyWildCard]s currently
/// assigned to this color.
class PropertySet {
  final PropertyColor color;
  final List<DealCard> cards = [];
  bool hasHouse = false;
  bool hasHotel = false;

  PropertySet(this.color);

  int get setSize => propertySetInfo[color]!.setSize;
  bool get isComplete => cards.length >= setSize;

  /// Railroad and Utility sets can never take a House/Hotel.
  bool get canHaveBuildings => color != PropertyColor.railroad && color != PropertyColor.utility;

  int get baseRent => propertySetInfo[color]!.rentFor(cards.length);

  int get rent {
    var r = baseRent;
    if (isComplete && canHaveBuildings) {
      if (hasHouse) r += 3;
      if (hasHotel) r += 4;
    }
    return r;
  }
}

class Player {
  final String id;
  final String name;
  final List<DealCard> hand = [];
  final List<DealCard> bank = [];
  final Map<PropertyColor, PropertySet> properties = {};

  Player({required this.id, required this.name});

  int get bankTotal => bank.fold(0, (sum, c) => sum + c.bankValue);

  int get completeSetCount => properties.values.where((s) => s.isComplete).length;

  bool get hasWon => completeSetCount >= 3;

  /// All assets a player can be forced to give up to cover a payment:
  /// money-equivalent cards from the bank. (Properties are only
  /// surrendered when the bank can't cover the amount in full — that's
  /// handled by the payment-resolution step in the turn engine, not here.)
  List<DealCard> get bankCardsSortedBySmallestFirst =>
      [...bank]..sort((a, b) => a.bankValue.compareTo(b.bankValue));
}

enum TurnPhase { draw, play, discard, over }

class GameState {
  final List<Player> players;
  int currentPlayerIndex = 0;
  final List<DealCard> drawPile;
  final List<DealCard> discardPile = [];
  TurnPhase phase = TurnPhase.draw;

  /// Cards played toward this turn's 3-card limit. Responses (e.g. Just Say
  /// No played against an opponent's action) do NOT count toward this and
  /// are handled separately once action resolution is implemented.
  int actionsPlayedThisTurn = 0;

  static const maxActionsPerTurn = 3;
  static const maxHandSize = 7;
  static const cardsDrawnPerTurn = 2;

  GameState({required this.players, required this.drawPile});

  Player get currentPlayer => players[currentPlayerIndex];

  Player? get winner {
    for (final p in players) {
      if (p.hasWon) return p;
    }
    return null;
  }

  /// Draws [count] cards from the draw pile, reshuffling the discard pile
  /// back in (Fisher-Yates, caller supplies [random] for determinism in
  /// tests) if the draw pile runs out.
  List<DealCard> drawCards(int count, {required Random random}) {
    final drawn = <DealCard>[];
    for (var i = 0; i < count; i++) {
      if (drawPile.isEmpty) {
        if (discardPile.isEmpty) break; // no cards left anywhere
        drawPile.addAll(discardPile);
        discardPile.clear();
        drawPile.shuffle(random);
      }
      drawn.add(drawPile.removeLast());
    }
    return drawn;
  }
}
