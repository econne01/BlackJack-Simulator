import os
import sys
from random import shuffle, uniform

from importer.StrategyImporter import StrategyImporter


SHOE_COUNT = 50
SHOE_SIZE = 6
SHOE_PENETRATION = 0.2
DECK_SIZE = 52.0
PLAYER_COUNT = 6
CARDS = {"Ace": 11, "Two": 2, "Three": 3, "Four": 4, "Five": 5, "Six": 6, "Seven": 7, "Eight": 8, "Nine": 9, "Ten": 10, "Jack": 10, "Queen": 10, "King": 10}

HARD_STRATEGY = {}
SOFT_STRATEGY = {}
PAIR_STRATEGY = {}


class HouseRules(object):
    """
    List of Blackjack game settings that can vary from casino to casino
    """
    # MAX_SPLITS = 3
    MAX_SPLIT_HANDS = 4
    HIT_SOFT_17 = True
    ALLOW_RESPLIT_ACES = False
    ALLOW_DOUBLE_AFTER_SPLIT = True


HOUSE_RULES = HouseRules()


class IncompleteHandException(Exception):
    pass


class Card(object):
    """
    Represents a playing card with name and value.
    """
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def __str__(self):
        return "%s" % self.name


class Shoe(object):
    """
    Represents the shoe, which consists of a number of card decks.
    """
    reshuffle = False

    def __init__(self, decks):
        self.decks = decks
        self.cards = self.init_cards()
        self.penetration_threshold = uniform(0.15, 0.25)

    def __str__(self):
        s = ""
        for c in self.cards:
            s += "%s\n" % c
        return s

    def init_cards(self):
        """
        Initialize the shoe with shuffled playing cards.
        """
        cards = []
        for d in range(self.decks):
            for c in CARDS:
                for i in range(0, 4):
                    cards.append(Card(c, CARDS[c]))
        shuffle(cards)
        return cards

    def deal(self):
        """
        Returns:    The next card off the shoe. If the shoe penetration is reached,
                    the shoe gets reshuffled.
        """
        if (len(self.cards) / (DECK_SIZE * self.decks)) < self.penetration_threshold:
            self.reshuffle = True
        return self.cards.pop()


class Hand(object):
    """
    Represents a hand, either from the dealer or from the player
    """
    _value = 0
    _aces = []
    _aces_soft = 0
    splithand = False
    surrender = False
    doubled = False

    def __init__(self, cards):
        self.cards = cards

    def __str__(self):
        h = ""
        for c in self.cards:
            h += "%s " % c
        return h

    @property
    def value(self):
        """
        Returns: The current value of the hand (aces are either counted as 1 or 11).
        """
        self._value = 0
        for c in self.cards:
            self._value += c.value

        if self._value > 21 and self.aces_soft > 0:
            for ace in self.aces:
                if ace.value == 11:
                    self._value -= 10
                    ace.value = 1
                    if self._value <= 21:
                        break

        return self._value

    @property
    def aces(self):
        """
        Returns: The all aces in the current hand.
        """
        self._aces = []
        for c in self.cards:
            if c.name == "Ace":
                self._aces.append(c)
        return self._aces

    @property
    def aces_soft(self):
        """
        Returns: The number of aces valued as 11
        """
        self._aces_soft = 0
        for ace in self.aces:
            if ace.value == 11:
                self._aces_soft += 1
        return self._aces_soft

    def soft(self):
        """
        Determines whether the current hand is soft (soft means that it consists of aces valued at 11).
        """
        if self.aces_soft > 0:
            return True
        else:
            return False

    def splitable(self):
        """
        Determines if the current hand can be splitted.
        """
        if self.length() == 2 and self.cards[0].name == self.cards[1].name:
            return True
        else:
            return False

    def can_double(self):
        return (self.length() == 2 and
                ((self.splithand and self.cards[0].value not in [10, 11])
                 or not self.splithand))

    def blackjack(self):
        """
        Check a hand for a blackjack.
        """
        if self.value == 21:
            if self.length() == 2 and not self.splithand:
                return True
            else:
                return False
        else:
            return False

    def busted(self):
        """
        Checks if the hand is busted.
        """
        if self.value > 21:
            return True
        else:
            return False

    def add_card(self, card):
        """
        Add a card to the current hand.
        """
        self.cards.append(card)

    def split(self):
        """
        Split the current hand.
        Returns: The new hand created from the split.
        """
        self.splithand = True
        c = self.cards.pop()
        new_hand = Hand([c])
        new_hand.splithand = True
        return new_hand

    def length(self):
        """
        Returns: The number of cards in the current hand.
        """
        return len(self.cards)

    def get_winner_status(self, dealer_hand):
        """
        Return hand winner status, one of "Win", "Lose" or "Push"
        """
        if self.length() < 2 or dealer_hand.length() < 2:
            raise IncompleteHandException('At least one of these hands has not completed playing')

        status = None
        if self.surrender or self.busted():
            status = 'LOSE'
        elif dealer_hand.busted():
            status = 'WIN'
        elif self.blackjack() and not dealer_hand.blackjack():
            status = 'WIN'
        elif not self.blackjack() and dealer_hand.blackjack():
            status = 'LOSE'
        elif self.blackjack() and dealer_hand.blackjack():
            status = 'PUSH'
        elif dealer_hand.value < self.value:
            status = 'WIN'
        elif dealer_hand.value > self.value:
            status = 'LOSE'
        elif dealer_hand.value == self.value:
            status = 'PUSH'
        return status

    def get_winning_multiplier(self, dealer_hand):
        """
        Return hand's winnings multiplier as a decimal
        @example get_winning_multiplier(<Hand>) => 1.5
        """
        winner_status = self.get_winner_status(dealer_hand)
        multiplier = 0.0
        if winner_status == 'LOSE' and self.surrender:
            multiplier = -0.5
        elif winner_status == 'LOSE':
            multiplier = -1.0
        elif winner_status == 'PUSH':
            multiplier = 0.0
        elif winner_status == 'WIN' and not self.blackjack():
            multiplier = 1.0
        elif winner_status == 'WIN' and self.blackjack():
            multiplier = 1.5

        if self.doubled:
            multiplier *= 2
        return multiplier


class Player(object):
    """
    Represent a player
    """
    def __init__(self, hand, dealer_hand, shoe):
        self.hands = [hand]
        self.dealer_hand = dealer_hand
        self.shoe = shoe

    def play(self):
        for hand in self.hands:
            print "Playing Hand: %s" % hand
            self.play_hand(hand)

    def can_split(self, hand):
        return (hand.splitable() and
                len(self.hands) < HOUSE_RULES.MAX_SPLIT_HANDS and
                (len(self.hands) == 1 or len(hand.aces) < 2))

    def play_hand(self, hand):
        if hand.length() < 2:
            if hand.cards[0].name == "Ace":
                hand.cards[0].value = 11
            self.hit(hand)

        while not hand.busted() and not hand.blackjack():
            if self.can_split(hand):
                if len(hand.aces) == 2:
                    flag = PAIR_STRATEGY[22][dealer_hand.cards[0].name]
                else:
                    flag = PAIR_STRATEGY[hand.value][dealer_hand.cards[0].name]
            elif hand.soft():
                flag = SOFT_STRATEGY[hand.value][dealer_hand.cards[0].name]
            else:
                flag = HARD_STRATEGY[hand.value][dealer_hand.cards[0].name]

            if flag == 'D':
                if hand.can_double():
                    print "Double Down"
                    hand.doubled = True
                    self.hit(hand)
                    break
                else:
                    flag = 'H'

            if flag == 'Sr':
                if hand.length() == 2:
                    print "Surrender"
                    hand.surrender = True
                    break
                else:
                    flag = 'H'

            if flag == 'H':
                self.hit(hand)
                
            if flag == 'P':
                self.split(hand)
                
            if flag == 'S': 
                break                   

    def hit(self, hand):
        c = self.shoe.deal()
        hand.add_card(c)
        print "Hitted: %s" % c

    def split(self, hand):
        self.hands.append(hand.split())
        print "Splitted %s" % hand
        self.play_hand(hand)


class Dealer(object):
    """
    Represent the dealer
    """
    def __init__(self, hand, shoe):
        self.hand = hand
        self.shoe = shoe

    def play(self):
        while self.hand.value < 17:
            self.hit()

    def hit(self):
        c = self.shoe.deal()
        self.hand.add_card(c)
        print "Dealer hitted: %s" %c


class DataLogger(object):
    """
    Write hand outcome statistics
    """
    def __init__(self, filename):
        current_directory = os.path.dirname(os.path.realpath(__file__))
        filename = current_directory + '/' + filename
        self.output_file = open(filename, 'w')
        self.write_headers()

    def write_headers(self):
        headers = ['Shoe Id', 'Deal Number','Player','Hand Number',
                   'Player Cards','Value','Player BJ','Double?','Split?','Bust?',
                   'Dealer Cards','Dealer Value','Dealer BJ','Dealer Bust?',
                   'Outcome','Multiplier']
        self.output_file.write(','.join(headers) + '\n')

    def log_deal(self, shoe_id, deal_id, players):
        hand_idx = 0
        for player_idx, player in enumerate(players):
            for hand in player.hands:
                data_row = [shoe_id, deal_id, player_idx, hand_idx,
                            str(hand), hand.value, hand.blackjack(),
                            hand.doubled, hand.splithand,hand.busted(),
                            str(player.dealer_hand), player.dealer_hand.value, player.dealer_hand.blackjack(),
                            player.dealer_hand.busted(),
                            hand.get_winner_status(player.dealer_hand),
                            hand.get_winning_multiplier(player.dealer_hand)]
                # Convert data to desired output format (ie, just '' instead of 'False')
                data_row = [str(elem).strip() for elem in data_row]
                data_row = [elem if elem != 'False' else '' for elem in data_row]
                # Write data
                self.output_file.write(','.join(data_row) + '\n')
                hand_idx += 1

    def close(self):
        self.output_file.close()


if __name__ == "__main__":
    importer = StrategyImporter(sys.argv[1])
    data_logger = DataLogger(sys.argv[2])
    HARD_STRATEGY, SOFT_STRATEGY, PAIR_STRATEGY = importer.import_player_strategy()

    shoe = Shoe(SHOE_SIZE)
    shoe_iteration = 0
    deal_iteration = 0

    while shoe_iteration < SHOE_COUNT:
        players = []
        starting_cards = []
        dealer_cards = []
        #---- Initialize the starting hand for each player ----#
        for index in xrange(PLAYER_COUNT):
            starting_cards.append([])

        #---- Deal for each player and Dealer ----#
        for card_count in xrange(2):
            for index in xrange(PLAYER_COUNT):
                starting_cards[index].append(shoe.deal())
            dealer_cards.append(shoe.deal())

        dealer_hand = Hand(dealer_cards)
        dealer = Dealer(dealer_hand, shoe)
        print "Dealer Hand: %s" % dealer.hand
        for index in xrange(PLAYER_COUNT):
            player_hand = Hand(starting_cards[index])
            players.append(Player(player_hand, dealer_hand, shoe))

        if not dealer_hand.blackjack():
            # Play only continues if dealer does not have Blackjack
            for player in players:
                player.play()
            dealer.play()

        # ----- Log outcomes -----#
        data_logger.log_deal(shoe_iteration, deal_iteration, players)
        deal_iteration += 1

        if shoe.reshuffle:
            print "\nReshuffle Shoe"
            shoe_iteration += 1
            shoe.reshuffle = False
            shoe.cards = shoe.init_cards()

    data_logger.close()
