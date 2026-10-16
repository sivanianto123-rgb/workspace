import 'package:monopoly_deal_engine/monopoly_deal_engine.dart';
import 'package:test/test.dart';

void main() {
  group('startNewGame', () {
    test('rejects player counts outside 2-5', () {
      expect(
        () => startNewGame(playerNames: ['solo'], allCards: buildFullDeck(), random: Random(1)),
        throwsA(isA<IllegalMoveException>()),
      );
      expect(
        () => startNewGame(
          playerNames: List.generate(6, (i) => 'p$i'),
          allCards: buildFullDeck(),
          random: Random(1),
        ),
        throwsA(isA<IllegalMoveException>()),
      );
    });

    test('deals 5 cards to each of N players and leaves the rest in the draw pile', () {
      final state = startNewGame(
        playerNames: ['Alice', 'Bob', 'Cara'],
        allCards: buildFullDeck(),
        random: Random(42),
      );
      expect(state.players.length, 3);
      for (final p in state.players) {
        expect(p.hand.length, 5);
      }
      expect(state.drawPile.length, 108 - 15);
    });
  });

  group('TurnEngine basic flow', () {
    late var state = startNewGame(
      playerNames: ['Alice', 'Bob'],
      allCards: buildFullDeck(),
      random: Random(7),
    );
    late var engine = TurnEngine(state, random: Random(7));

    setUp(() {
      state = startNewGame(playerNames: ['Alice', 'Bob'], allCards: buildFullDeck(), random: Random(7));
      engine = TurnEngine(state, random: Random(7));
    });

    test('startTurn draws 2 cards and moves to play phase', () {
      final before = state.currentPlayer.hand.length;
      engine.startTurn();
      expect(state.currentPlayer.hand.length, before + 2);
      expect(state.phase, TurnPhase.play);
    });

    test('cannot play more than 3 cards per turn', () {
      engine.startTurn();
      final player = state.currentPlayer;
      // Stack the hand with 4 money cards so we don't run out mid-test.
      player.hand
        ..clear()
        ..addAll(List.generate(4, (i) => MoneyCard(id: 'm$i', bankValue: 1)));

      engine.playToBank(player.hand[0]);
      engine.playToBank(player.hand[0]);
      engine.playToBank(player.hand[0]);
      expect(() => engine.playToBank(player.hand[0]), throwsA(isA<IllegalMoveException>()));
      expect(player.bank.length, 3);
    });

    test('playing a property card adds it to the right color set', () {
      engine.startTurn();
      final player = state.currentPlayer;
      final card = PropertyCard(id: 'bp1', bankValue: 1, name: 'Baltic Avenue', color: PropertyColor.brown);
      player.hand.add(card);

      engine.playToProperty(card);

      expect(player.properties[PropertyColor.brown]!.cards, contains(card));
      expect(player.properties[PropertyColor.brown]!.isComplete, isFalse);
    });

    test('completing a 3-set win condition after 3 full sets', () {
      engine.startTurn();
      final player = state.currentPlayer;

      void completeSet(PropertyColor color) {
        final info = propertySetInfo[color]!;
        for (var i = 0; i < info.setSize; i++) {
          final card = PropertyCard(id: '${color.name}-$i', bankValue: 1, name: '${color.name} $i', color: color);
          player.hand.add(card);
          player.properties.putIfAbsent(color, () => PropertySet(color)).cards.add(card);
          player.hand.remove(card);
        }
      }

      expect(player.hasWon, isFalse);
      completeSet(PropertyColor.brown);
      completeSet(PropertyColor.darkBlue);
      expect(player.hasWon, isFalse);
      completeSet(PropertyColor.utility);
      expect(player.hasWon, isTrue);
      expect(state.winner, same(player));
    });

    test('endTurn discards down to 7 cards and advances the turn', () {
      engine.startTurn();
      final player = state.currentPlayer;
      player.hand
        ..clear()
        ..addAll(List.generate(9, (i) => MoneyCard(id: 'm$i', bankValue: 1)));

      final startIndex = state.currentPlayerIndex;
      engine.endTurn();

      expect(player.hand.length, 7);
      expect(state.discardPile.length, 2);
      expect(state.currentPlayerIndex, (startIndex + 1) % state.players.length);
      expect(state.phase, TurnPhase.draw);
    });

    test('moveWildcard reassigns an in-play wildcard to a new eligible color', () {
      engine.startTurn();
      final player = state.currentPlayer;
      final wild = PropertyWildCard(
        id: 'w1',
        bankValue: 1,
        eligibleColors: {PropertyColor.lightBlue, PropertyColor.brown},
      );
      player.hand.add(wild);
      engine.playToProperty(wild, chosenColor: PropertyColor.brown);
      expect(player.properties[PropertyColor.brown]!.cards, contains(wild));

      engine.moveWildcard(wild, PropertyColor.lightBlue);

      expect(player.properties[PropertyColor.brown]!.cards, isNot(contains(wild)));
      expect(player.properties[PropertyColor.lightBlue]!.cards, contains(wild));
    });
  });
}
