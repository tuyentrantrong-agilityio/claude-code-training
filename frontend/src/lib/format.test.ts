import { fmtT, greeting, initials, tone } from './format';

describe('fmtT', () => {
  it('formats seconds as mm:ss', () => {
    expect(fmtT(0)).toBe('00:00');
    expect(fmtT(65)).toBe('01:05');
    expect(fmtT(612.9)).toBe('10:12');
    expect(fmtT(3600)).toBe('60:00');
  });
  it('clamps negatives to zero', () => {
    expect(fmtT(-5)).toBe('00:00');
  });
});

describe('initials', () => {
  it('uses the first letters of up to two words', () => {
    expect(initials('Alex Rivera')).toBe('AR');
    expect(initials('  northwind studio  ')).toBe('NS');
    expect(initials('Maya')).toBe('M');
    expect(initials('Ann Marie Lee')).toBe('AM');
    expect(initials('')).toBe('');
  });
});

describe('tone', () => {
  it('is stable and within 0..4', () => {
    expect(tone('Alex Rivera')).toBe(tone('Alex Rivera'));
    for (const n of ['a', 'Maya Chen', 'Northwind Studio', 'Priya Nair', 'x'.repeat(40)]) {
      const t = tone(n);
      expect(Number.isInteger(t)).toBe(true);
      expect(t).toBeGreaterThanOrEqual(0);
      expect(t).toBeLessThan(5);
    }
  });
  it('matches the known hash for a sample', () => {
    // 'a' = 97 -> 97 % 5 = 2
    expect(tone('a')).toBe(2);
  });
});

describe('greeting', () => {
  it('depends on the hour', () => {
    expect(greeting(new Date(2026, 0, 1, 8))).toBe('Good morning');
    expect(greeting(new Date(2026, 0, 1, 13))).toBe('Good afternoon');
    expect(greeting(new Date(2026, 0, 1, 20))).toBe('Good evening');
  });
});
