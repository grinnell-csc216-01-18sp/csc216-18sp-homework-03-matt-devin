##
# CSC 216 (Spring 2018)
# Reliable Transport Protocols (Homework 3)
#
# Sender-receiver code for the RDP simulation program.  You should provide
# your implementation for the homework in this file.
#
# Your various Sender implementations should inherit from the BaseSender
# class which exposes the following important methods you should use in your
# implementations:
#
# - sender.send_to_network(seg): sends the given segment to network to be
#   delivered to the appropriate recipient.
# - sender.start_timer(interval): starts a timer that will fire once interval
#   steps have passed in the simulation.  When the timer expires, the sender's
#   on_interrupt() method is called (which should be overridden in subclasses
#   if timer functionality is desired)
#
# Your various Receiver implementations should also inherit from the
# BaseReceiver class which exposes thef ollowing important methouds you should
# use in your implementations:
#
# - sender.send_to_network(seg): sends the given segment to network to be
#   delivered to the appropriate recipient.
# - sender.send_to_app(msg): sends the given message to receiver's application
#   layer (such a message has successfully traveled from sender to receiver)
#
# Subclasses of both BaseSender and BaseReceiver must implement various methods.
# See the NaiveSender and NaiveReceiver implementations below for more details.
##

from sendrecvbase import BaseSender, BaseReceiver

import Queue
import random

class Segment:
    def __init__(self, msg, dst, msg_id=None):
        self.msg = msg
        self.dst = dst
        self.msg_id = msg_id
        self.syn = None
        self.fin = None

class NaiveSender(BaseSender):
    def __init__(self, app_interval):
        super(NaiveSender, self).__init__(app_interval)

    def receive_from_app(self, msg):
        seg = Segment(msg, 'receiver')
        self.send_to_network(seg)

    def receive_from_network(self, seg):
        pass    # Nothing to do!

    def on_interrupt(self):
        pass    # Nothing to do!

class NaiveReceiver(BaseReceiver):
    def __init__(self):
        super(NaiveReceiver, self).__init__()

    def receive_from_client(self, seg):
        self.send_to_app(seg.msg)

class AltSender(BaseSender):
    def __init__(self, app_interval):
        super(AltSender, self).__init__(app_interval)
        self.bit = True
        self.last_seg = Segment('', '', '')

    def tcp_handshake(self):
        self.bit = random.randint(0, 1)
        seg = Segment("", 'receiver', self.bit)
        seg.syn = 1
        self.send_to_network(seg)
        self.bit = not self.bit

    def tcp_handshake_part_three(self, seg):
        new_seg = Segment('Connection established', 'receiver', self.bit)
        copy_seg = Segment('Connection established', 'receiver', self.bit)
        self.last_seg = copy_seg
        self.send_to_network(new_seg)
        self.connected = True
        print("Connected: {}".format(self.connected))

    def tcp_close(self):
        seg = Segment('', 'receiver', self.bit)
        seg.fin = 1
        self.send_to_network(seg)

    def tcp_close_ack(self, seg):
        if seg.fin != 1:
            return

        self.connected = False
        print("Sender connected: {}".format(self.connected))

    def receive_from_app(self, msg):
        seg = Segment(msg, 'receiver', self.bit)
        seg_cpy = Segment(msg, 'receiver', self.bit)
        self.send_to_network(seg)
        self.last_seg = seg_cpy
        self.start_timer(self.app_interval)
        self.disallow_app_msgs()

    def receive_from_network(self, seg):
        if seg.msg == "<CORRUPTED>":
            self.on_interrupt()

        if seg.msg_id == self.bit and seg.msg == "ACK":
            self.bit = not self.bit
            self.end_timer()
            self.allow_app_msgs()
        
        elif seg.msg_id != self.bit and seg.msg == "ACK":
            self.on_interrupt()
   
    def on_interrupt(self):
        new_seg = Segment(self.last_seg.msg, 'receiver', self.last_seg.msg_id)
        self.send_to_network(new_seg)
        self.start_timer(self.app_interval)

class AltReceiver(BaseReceiver):
    def __init__(self):
        super(AltReceiver, self).__init__()
        self.bit = True

    def receive_from_client(self, seg):
        if seg.msg == "<CORRUPTED>":
            self.send_to_network(Segment("ACK", 'sender', not self.bit))
            return

        if seg.msg_id == self.bit:
            self.send_to_app(seg.msg)
            self.send_to_network(Segment("ACK", 'sender', self.bit))
            self.bit = not self.bit

        else:
            self.send_to_network(Segment("ACK", 'sender', not self.bit))

    def tcp_handshake(self, seg):
        self.bit = seg.msg_id
        self.bit = not self.bit
        new_seg = Segment('ACK', 'sender', self.bit)
        new_seg.syn = 1
        self.send_to_network(new_seg)

    def tcp_close(self):
        seg = Segment('', 'sender', self.bit)
        seg.fin = 1
        self.send_to_network(seg)

    def tcp_close_ack(self, seg):
        if seg.fin != 1:
            return

        self.connected = False
        print("Receiver connected: {}".format(self.connected))

class GBNSender(BaseSender):
    def __init__(self, app_interval, **args):
        super(GBNSender, self).__init__(app_interval)

        self.seq_num = 0
        self.base = 0
        if 'n' in args:
            self.n = args.get('n')
        else: 
            self.n = 3
        
        self.last_n = [None]*self.n

    def receive_from_app(self, msg):
        if self.seq_num < self.base + self.n:
            seg = Segment(msg, 'receiver', self.seq_num)
            seg_copy = Segment(msg, 'receiver', self.seq_num)
            self.last_n[self.seq_num % self.n] = seg_copy 
            self.send_to_network(seg)
            if self.seq_num == self.base:
                self.start_timer(self.app_interval)
            self.seq_num += 1
            if self.seq_num == self.base + self.n:
                self.disallow_app_msgs()

    def receive_from_network(self, seg):
        if seg.msg == "<CORRUPTED>":
            return

        # not corrupt
        self.base = seg.msg_id+1
        if self.seq_num - self.base < self.n:
            self.allow_app_msgs()
        
        if self.base == self.seq_num:
            self.end_timer()
        else:
            self.start_timer(self.app_interval)

    def on_interrupt(self):
        for ind in range(self.seq_num - self.n, self.seq_num):
            seg = self.last_n[ind % self.n]
            if seg != None:
                new_seg = Segment(seg.msg, 'receiver', seg.msg_id)
                self.send_to_network(new_seg) 
        self.start_timer(self.app_interval)

    def tcp_handshake(self):
        self.base = random.randint(0, 50)
        self.seq_num = self.base
        seg = Segment("", 'receiver', self.seq_num)
        seg.syn = 1
        self.send_to_network(seg)
        self.seq_num += 1

    def tcp_handshake_part_three(self, seg):
        self.base = seg.msg_id+1
        new_seg = Segment('Connection established', 'receiver', self.seq_num)
        copy_seg = Segment('Connection established', 'receiver', self.seq_num)
        self.last_seg = copy_seg
        self.send_to_network(new_seg)
        self.connected = True
        print("Connected: {}".format(self.connected))

    def tcp_close(self):
        seg = Segment('', 'receiver', self.seq_num)
        seg.fin = 1
        self.send_to_network(seg)

    def tcp_close_ack(self, seg):
        if seg.fin != 1:
            return

        self.connected = False
        print("Sender connected: {}".format(self.connected))

class GBNReceiver(BaseReceiver):
    def __init__(self):
        super(GBNReceiver, self).__init__()
        self.seq_num = 0

    def receive_from_client(self, seg):
        if seg.msg == "<CORRUPTED>" or seg.msg_id != self.seq_num:
            self.send_to_network(Segment("ACK", 'sender', self.seq_num-1))
            return

        if seg.msg_id == self.seq_num:
            self.send_to_app(seg.msg)
            self.send_to_network(Segment("ACK", 'sender', self.seq_num))
            self.seq_num = self.seq_num + 1

    def tcp_handshake(self, seg):
        self.seq_num = seg.msg_id
        new_seg = Segment('ACK', 'sender', self.seq_num)
        new_seg.syn = 1
        self.send_to_network(new_seg)
        self.seq_num += 1
        self.connected = True

    def tcp_close(self):
        seg = Segment('', 'sender', self.seq_num)
        seg.fin = 1
        self.send_to_network(seg)

    def tcp_close_ack(self, seg):
        if seg.fin != 1:
            return

        self.connected = False
        print("Receiver connected: {}".format(self.connected))

