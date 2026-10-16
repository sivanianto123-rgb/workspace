# Monopoly Deal

A Monopoly Deal app for iOS and Android with online multiplayer.

## Architecture

- **`engine/`** — pure Dart package with the rules engine (cards, deck,
  game state, turn logic, action-card effects). No UI, no networking.
  Shared by both the client and the server so the rules only exist in one
  place.
- **`app/`** — Flutter client (iOS + Android), not started yet.
- **`server/`** — Dart backend (matchmaking, authoritative game state,
  realtime sync over WebSocket), not started yet. Depends on `engine/` as
  a path dependency, same as `app/` will.

Using Dart end-to-end (engine + server) means the client and server never
have two separate reimplementations of the rules to keep in sync.

## Status

Built so far, in `engine/`:
- Full 108-card deck (money, properties, property wildcards, rent cards,
  action cards) with exact official counts/values.
- Game state (players, hands, banks, in-play property sets, draw/discard
  piles).
- Basic turn flow: deal, draw 2, play up to 3 cards/turn (to bank or to a
  property set), move wildcards between colors, discard to the 7-card hand
  limit, win detection (3 complete property sets).

Not yet implemented:
- Action card *effects* (Sly Deal, Forced Deal, Deal Breaker, Debt
  Collector, It's My Birthday, Pass Go, House/Hotel rent bonus, Rent
  collection, Double The Rent, Just Say No responses).
- Networking/server, matchmaking, auth.
- Flutter UI.

## Running the engine tests

```sh
cd engine
dart pub get
dart test
```

## Deck reference

Source: https://monopolydealrules.com/index.php?page=play (official counts
confirmed from that page's photographed cards, Oct 2026). One discrepancy
worth noting: that page's "34 Action Cards" section header doesn't match
the sum of the per-card counts it lists right below it (2+3+3+4+3+3+10+3+3+2
= 36). The engine uses the itemized per-card counts (36), since those are
individually tied to named cards; this makes the full deck 108 cards
rather than the site's stated 106. If you can confirm which number is the
typo, update `engine/lib/src/deck.dart` and the counts in
`engine/README` references accordingly.

Red, Yellow, and Utility property prices/rents use the standard published
values (the source page's screenshots cut off before showing those three
colors) rather than a screenshot-confirmed source — everything else was
read directly off photographed cards.
