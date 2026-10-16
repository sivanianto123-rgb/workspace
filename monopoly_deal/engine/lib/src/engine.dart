import 'cards.dart';
import 'game_state.dart';

/// Thrown when a requested move is illegal given the current [GameState].
/// The server/UI layer is expected to catch this and reject the move
/// rather than let it crash a turn.
class IllegalMoveException implements Exception {
  final String message;
  IllegalMoveException(this.message);
  @override
  String toString() => 'IllegalMoveException: $message';
}

/// Deals a fresh game: shuffles a full deck and gives each player 5 cards.
/// `allCards` is injected so tests/the server can pass `buildFullDeck()`
/// explicitly rather than this function owning deck construction.
GameState startNewGame({
  required List<String> playerNames,
  required List<DealCard> allCards,
  required Random random,
}) {
  if (playerNames.length < 2 || playerNames.length > 5) {
    throw IllegalMoveException('Monopoly Deal supports 2-5 players, got ${playerNames.length}.');
  }
  final deck = [...allCards]..shuffle(random);
  final players = [
    for (var i = 0; i < playerNames.length; i++) Player(id: 'p$i', name: playerNames[i]),
  ];
  final state = GameState(players: players, drawPile: deck);
  for (final p in players) {
    p.hand.addAll(state.drawCards(5, random: random));
  }
  state.phase = TurnPhase.draw;
  return state;
}

/// This is the basic turn skeleton: draw, play cards to bank/property,
/// discard to the hand limit, win check. Action-card *effects* (Sly Deal,
/// Deal Breaker, rent collection, Just Say No, etc.) are the next
/// milestone — `playActionCard` below only validates the 3-card limit and
/// moves the card to the discard pile; it does not yet resolve what the
/// action does.
class TurnEngine {
  final GameState state;
  final Random random;

  TurnEngine(this.state, {Random? random}) : random = random ?? Random();

  Player get _current => state.currentPlayer;

  /// Must be called once at the start of a player's turn before any other
  /// move. Draws 2 cards from the draw pile.
  void startTurn() {
    if (state.phase != TurnPhase.draw) {
      throw IllegalMoveException('Turn already started (phase=${state.phase}).');
    }
    _current.hand.addAll(state.drawCards(GameState.cardsDrawnPerTurn, random: random));
    state.actionsPlayedThisTurn = 0;
    state.phase = TurnPhase.play;
  }

  void _requireCardInHand(DealCard card) {
    if (!_current.hand.contains(card)) {
      throw IllegalMoveException('${card.id} is not in ${_current.name}\'s hand.');
    }
  }

  void _requireActionBudget() {
    if (state.actionsPlayedThisTurn >= GameState.maxActionsPerTurn) {
      throw IllegalMoveException('Already played ${GameState.maxActionsPerTurn} cards this turn.');
    }
  }

  /// Plays a money-valued card (a [MoneyCard], or any [ActionCard]/[RentCard]
  /// used purely for its bank value) face-up into the player's bank.
  void playToBank(DealCard card) {
    if (state.phase != TurnPhase.play) {
      throw IllegalMoveException('Not in the play phase (phase=${state.phase}).');
    }
    _requireCardInHand(card);
    _requireActionBudget();
    if (card is PropertyCard || card is PropertyWildCard) {
      throw IllegalMoveException('Property cards cannot be banked; play them to a property set instead.');
    }
    _current.hand.remove(card);
    _current.bank.add(card);
    state.actionsPlayedThisTurn++;
  }

  /// Plays a [PropertyCard] or [PropertyWildCard] face-up as real estate.
  /// [chosenColor] is required for wildcards (and must be one of
  /// [PropertyWildCard.eligibleColors]); it's ignored for plain
  /// [PropertyCard]s, which always go to their own color.
  void playToProperty(DealCard card, {PropertyColor? chosenColor}) {
    if (state.phase != TurnPhase.play) {
      throw IllegalMoveException('Not in the play phase (phase=${state.phase}).');
    }
    _requireCardInHand(card);
    _requireActionBudget();

    final PropertyColor color;
    if (card is PropertyCard) {
      color = card.color;
    } else if (card is PropertyWildCard) {
      if (chosenColor == null || !card.eligibleColors.contains(chosenColor)) {
        throw IllegalMoveException('Must choose a color from ${card.eligibleColors} for this wildcard.');
      }
      color = chosenColor;
    } else {
      throw IllegalMoveException('${card.runtimeType} is not a property card.');
    }

    _current.hand.remove(card);
    _current.properties.putIfAbsent(color, () => PropertySet(color)).cards.add(card);
    state.actionsPlayedThisTurn++;
  }

  /// Re-assigns an in-play wildcard to a different eligible color, as long
  /// as it isn't currently part of a complete set (official rule: you can
  /// move a wildcard between colors freely otherwise). This does not cost
  /// one of the 3 turn actions.
  void moveWildcard(PropertyWildCard card, PropertyColor newColor) {
    if (!card.eligibleColors.contains(newColor)) {
      throw IllegalMoveException('${card.id} cannot be assigned to ${newColor.name}.');
    }
    PropertyColor? currentColor;
    for (final entry in _current.properties.entries) {
      if (entry.value.cards.contains(card)) {
        currentColor = entry.key;
        break;
      }
    }
    if (currentColor == null) {
      throw IllegalMoveException('${card.id} is not currently in play for ${_current.name}.');
    }
    final fromSet = _current.properties[currentColor]!;
    if (fromSet.isComplete) {
      throw IllegalMoveException('Cannot move a wildcard out of a completed set.');
    }
    fromSet.cards.remove(card);
    _current.properties.putIfAbsent(newColor, () => PropertySet(newColor)).cards.add(card);
  }

  /// Plays an action card. For now this only enforces the 3-card limit and
  /// discards the card — it's a placeholder until each [ActionType]'s
  /// effect is implemented (next milestone).
  ActionCard playActionCardStub(ActionCard card) {
    if (state.phase != TurnPhase.play) {
      throw IllegalMoveException('Not in the play phase (phase=${state.phase}).');
    }
    _requireCardInHand(card);
    _requireActionBudget();
    _current.hand.remove(card);
    state.discardPile.add(card);
    state.actionsPlayedThisTurn++;
    return card;
  }

  /// Ends the current player's turn: discards down to the 7-card hand
  /// limit, advances to the next player, and resets turn-scoped counters.
  /// [discardChoices] picks which excess cards to discard when the hand is
  /// over the limit; if omitted, the engine discards arbitrarily from the
  /// end of the hand.
  void endTurn({List<DealCard>? discardChoices}) {
    if (state.phase != TurnPhase.play) {
      throw IllegalMoveException('Cannot end turn from phase=${state.phase}.');
    }
    state.phase = TurnPhase.discard;

    final excess = _current.hand.length - GameState.maxHandSize;
    if (excess > 0) {
      final toDiscard = discardChoices ?? _current.hand.sublist(_current.hand.length - excess);
      if (toDiscard.length != excess) {
        throw IllegalMoveException('Must discard exactly $excess card(s), got ${toDiscard.length}.');
      }
      for (final c in toDiscard) {
        _requireCardInHand(c);
      }
      for (final c in toDiscard) {
        _current.hand.remove(c);
        state.discardPile.add(c);
      }
    }

    if (state.winner != null) {
      state.phase = TurnPhase.over;
      return;
    }

    state.currentPlayerIndex = (state.currentPlayerIndex + 1) % state.players.length;
    state.phase = TurnPhase.draw;
  }
}
