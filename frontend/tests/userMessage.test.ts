import { describe,expect,it } from 'vitest';
import { fieldLabel,userMessage } from '../src/shared/lib/userMessage';
import { responseError } from '../src/shared/api/http';

describe('readable public warnings',()=>{
  it('explains legacy financial balance rules without variable names or operators',()=>{
    const message=userMessage('Показатели не согласованы: totalAssetsMinor>0, totalAssetsMinor=totalLiabilitiesMinor+equityMinor');
    expect(message).toContain('Сумма активов должна быть больше нуля');
    expect(message).toContain('суммой всех обязательств и собственного капитала');
    expect(message).not.toMatch(/[A-Za-z]|[<>=]/);
  });
  it('names missing financial fields and nested paths in Russian',()=>{
    expect(userMessage('Не заполнены показатели: financialStatement.values.revenueMinor, equityMinor')).toBe('Не заполнены показатели: Выручка, Собственный капитал');
    expect(fieldLabel('financialStatement.values.totalAssetsMinor')).toBe('Все активы');
    expect(fieldLabel('unrecognized.internalField')).toBe('Поле заявки');
  });
  it.each(['TypeError: Failed to fetch','Ошибка: unknownInternalVariable <= 0','SQL SELECT * FROM session','<html>private debug</html>'])('hides technical diagnostics: %s',message=>{
    const result=userMessage(message);
    expect(result).toContain('попробуйте ещё раз');
    expect(result).not.toMatch(/[A-Za-z]|[<>=]/);
  });
  it('preserves actionable Russian guidance',()=>{
    const text='Оборотные активы не могут превышать сумму всех активов';
    expect(userMessage(text)).toBe(text);
  });
  it('normalizes backend fieldErrors and hides internal validator text',async()=>{
    const error=await responseError(Response.json({message:'Validation failed',fieldErrors:[{field:'financialStatement.values.revenueMinor',message:'must be greater than 0'}]},{status:422}));
    expect(error.message).toBe('Проверьте заполнение полей');
    expect(error.fields['financialStatement.values.revenueMinor']).toBe('Проверьте значение этого поля');
  });
  it.each([null,[],{message:{internal:'details'},fieldErrors:{field:'path'}}])('handles malformed error payloads without displaying diagnostics',async body=>{
    const error=await responseError(Response.json(body,{status:422}));
    expect(error.message).toBe('Проверьте заполнение полей');
    expect(error.fields).toEqual({});
  });
});
