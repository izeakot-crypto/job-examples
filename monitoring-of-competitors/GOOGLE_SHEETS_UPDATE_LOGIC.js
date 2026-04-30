// Google Sheets Update/Insert Logic
// Цей код йде в новий Code node ПЕРЕД Save to Sheets1

const newData = $input.all()[0].json;
const company = newData['Компанія'];
const url = newData['URL'];

// Отримуємо всі існуючі рядки з Google Sheets через node "Get row(s) in sheet"
// Підключіть цей node до Google Sheets з operation "Get Many"
const existingRows = $('Get row(s) in sheet').all();

console.log('Checking for existing record:', company);
console.log('Total existing rows:', existingRows.length);

// Шукаємо чи є вже компанія в таблиці
let existingRowIndex = -1;
let existingRowId = null;

for (let i = 0; i < existingRows.length; i++) {
  const row = existingRows[i].json;

  // Перевіряємо по назві компанії або URL
  if (row['Компанія'] === company || row['URL'] === url) {
    existingRowIndex = i;
    existingRowId = row.id || row.rowNumber || (i + 2); // +2 бо Excel row number starts from 1 + header
    console.log('Found existing record at row:', existingRowId);
    break;
  }
}

// Якщо знайшли - позначаємо для UPDATE
if (existingRowIndex !== -1) {
  return {
    operation: 'update',
    rowId: existingRowId,
    data: newData,
    message: `Updating existing record for ${company}`
  };
} else {
  // Якщо не знайшли - позначаємо для INSERT
  return {
    operation: 'append',
    data: newData,
    message: `Creating new record for ${company}`
  };
}
