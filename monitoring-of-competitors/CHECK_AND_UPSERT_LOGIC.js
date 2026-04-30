// Check if company exists and prepare upsert
const formattedData = $input.item.json;
const company = formattedData['Компанія'];
const url = formattedData['URL'];

// Get all existing rows from Google Sheets (припускаємо що є node "Get All Rows from Sheets")
const existingRows = $('Get All Rows from Sheets').all();

// Шукаємо чи існує компанія
let existingRowIndex = -1;
let existingRowNumber = -1;

for (let i = 0; i < existingRows.length; i++) {
  const row = existingRows[i].json;
  // Порівнюємо по назві компанії або URL
  if (row['Компанія'] === company || row['URL'] === url) {
    existingRowIndex = i;
    existingRowNumber = i + 2; // +2 бо 1 = header row, і рядки починаються з 1
    break;
  }
}

return {
  json: {
    ...formattedData,
    _meta: {
      exists: existingRowIndex !== -1,
      rowNumber: existingRowNumber,
      action: existingRowIndex !== -1 ? 'update' : 'append'
    }
  }
};
