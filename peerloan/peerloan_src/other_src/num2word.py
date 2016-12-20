#!/usr/bin/python
#-*- encoding: utf-8 -*-

import types
import math
"""
class NotIntegerError(Exception):
  pass

class OutOfRangeError(Exception):
  pass

_MAPPING = (u'零', u'一', u'二', u'三', u'四', u'五', u'六', u'七', u'八', u'九', )
_P0 = (u'', u'十', u'百', u'千', )
_S4, _S8, _S16 = 10 ** 4 , 10 ** 8, 10 ** 16
_MIN, _MAX = 0, 9999999999999999

def _to_chinese4(num):
  '''转换[0, 10000)之间的阿拉伯数字
  '''
  assert(0 <= num and num < _S4)
  if num < 10:
    return _MAPPING[num]
  else:
    lst = [ ]
    while num >= 10:
      lst.append(num % 10)
      num = num / 10
    lst.append(num)
    c = len(lst)  # 位数
    result = u''
    
    for idx, val in enumerate(lst):
      if val != 0:
        result += _P0[idx] + _MAPPING[val]
        if idx < c - 1 and lst[idx + 1] == 0:
          result += u'零'
    
    return result[::-1].replace(u'一十', u'十')
    
def _to_chinese8(num):
  assert(num < _S8)
  to4 = _to_chinese4
  if num < _S4:
    return to4(num)
  else:
    mod = _S4
    high, low = num / mod, num % mod
    if low == 0:
      return to4(high) + u'萬'
    else:
      if low < _S4 / 10:
        return to4(high) + u'萬零' + to4(low)
      else:
        return to4(high) + u'萬' + to4(low)
      
def _to_chinese16(num):
  assert(num < _S16)
  to8 = _to_chinese8
  mod = _S8
  high, low = num / mod, num % mod
  if low == 0:
    return to8(high) + u'億'
  else:
    if low < _S8 / 10:
      return to8(high) + u'億零' + to8(low)
    else:
      return to8(high) + u'億' + to8(low)
    
def to_chinese(num):
  if type(num) != types.IntType and type(num) != types.LongType:
    raise NotIntegerError(u'%s is not a integer.' % num)
  if num < _MIN or num > _MAX:
    raise OutOfRangeError(u'%d out of range[%d, %d)' % (num, _MIN, _MAX))
  
  if num < _S4:
    return _to_chinese4(num)
  elif num < _S8:
    return _to_chinese8(num)
  else:
    return _to_chinese16(num)
"""

class Number2Word:
	
	NUMBER_WORDS = {
		0 : "Zero",
		1 : "One",
		2 : "Two",
		3 : "Three",
		4 : "Four",
		5 : "Five",
		6 : "Six",
		7 : "Seven",
		8 : "Eight",
		9 : "Nine",
		10 : "Ten",
		11 : "Eleven",
		12 : "Twelve",
		13 : "Thirteen",
		14 : "Fourteen",
		15 : "Fifteen",
		16 : "Sixteen",
		17 : "Seventeen",
		18 : "Eighteen",
		19 : "Nineteen",
		20 : "Twenty",
		30 : "Thirty",
		40 : "Forty",
		50 : "Fifty",
		60 : "Sixty",
		70 : "Seventy",
		80 : "Eighty",
		90 : "Ninety"
	}
	
	def int_to_english(self, n):
		n = int(n)
		
		english_parts = []
		ones = int(round(n % 10))
		tens = int(round(n % 100))
		hundreds = math.floor(n / 100) % 10
		thousands = math.floor(n / 1000)
		
		if thousands:
			english_parts.append(self.int_to_english(thousands))
			english_parts.append('Thousand')
			if not hundreds and tens:
				english_parts.append('and')
		if hundreds:
			english_parts.append(self.NUMBER_WORDS[hundreds])
			english_parts.append('Hundred')
			if tens:
				english_parts.append('and')
		if tens:
			if tens < 20 or ones == 0:
				english_parts.append(self.NUMBER_WORDS[tens])
			else:
				english_parts.append(self.NUMBER_WORDS[tens - ones])
				english_parts.append(self.NUMBER_WORDS[ones])
		return ' '.join(english_parts)
	
	def cent_to_english(self, n):
		english_parts = []
		cents = round((n - int(n)) * 100)
		tenths = int(round(cents % 100))
		hundredths = int(round(cents % 10))
		print cents, tenths, hundredths
		if tenths:
			if tenths < 20 or hundredths == 0:
				english_parts.append(self.NUMBER_WORDS[tenths])
			else:
				english_parts.append(self.NUMBER_WORDS[tenths - hundredths])
				english_parts.append(self.NUMBER_WORDS[hundredths])
		else:
			english_parts.append(self.NUMBER_WORDS[tenths])
		return ' '.join(english_parts)
	
	def float_to_dollar_english(self, n):
		int_english = self.int_to_english(n)
		cent_english = self.cent_to_english(n)
		english_parts = [int_english, 'Dollars', 'and', cent_english, 'Cents']
		return ' '.join(english_parts)
