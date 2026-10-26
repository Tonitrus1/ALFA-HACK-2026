import { describe,it,expect } from 'vitest';
import { minor } from '../src/shared/api/client';
import { toKopecks } from '../src/shared/lib/money';
describe('public financial precision',()=>{
 it('preserves signed amounts and exact safe boundary',()=>{expect(minor('90 071 992 547 409,91')).toBe(Number.MAX_SAFE_INTEGER);expect(minor('-0,01',true)).toBe(-1);expect(minor('-123,45',true)).toBe(-12345);});
 it('rejects blank, precision loss, unsafe integer, and unsigned negative',()=>{for(const x of ['',' ','1,001','90071992547409,92','-1'])expect(()=>minor(x)).toThrow();expect(toKopecks('0,29')).toBe('29');});
});
