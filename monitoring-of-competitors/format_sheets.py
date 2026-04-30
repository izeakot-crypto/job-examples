import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = r'[USER_HOME]\Downloads\noted-creek-481412-k7-57f228a0aece.json'
SPREADSHEET_ID = 'YOUR_SECRET_TOKEN'
SHEET_ID = 2127507893

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)

service = build('sheets', 'v4', credentials=credentials)

# Color definitions (RGB 0-1)
HEADER_TEXT = {'red': 1, 'green': 1, 'blue': 1}  # White
ROW_ALT_1 = {'red': 0.95, 'green': 0.97, 'blue': 1}  # Light blue
ROW_ALT_2 = {'red': 1, 'green': 1, 'blue': 1}  # White

# Category colors for header groups
CAT_BASIC = {'red': 0.11, 'green': 0.15, 'blue': 0.27}  # Dark navy - basic info
CAT_CONTENT = {'red': 0.0, 'green': 0.44, 'blue': 0.55}  # Teal - content
CAT_SOCIAL = {'red': 0.18, 'green': 0.49, 'blue': 0.2}  # Green - social
CAT_FEEDBACK = {'red': 0.76, 'green': 0.38, 'blue': 0.08}  # Orange - feedback
CAT_AI = {'red': 0.42, 'green': 0.18, 'blue': 0.57}  # Purple - AI

requests = [
    # 1. Freeze header row
    {
        'updateSheetProperties': {
            'properties': {
                'sheetId': SHEET_ID,
                'gridProperties': {'frozenRowCount': 1}
            },
            'fields': 'gridProperties.frozenRowCount'
        }
    },

    # 2. Set column widths - Date
    {'updateDimensionProperties': {
        'range': {'sheetId': SHEET_ID, 'dimension': 'COLUMNS', 'startIndex': 0, 'endIndex': 1},
        'properties': {'pixelSize': 100}, 'fields': 'pixelSize'
    }},
    # Company
    {'updateDimensionProperties': {
        'range': {'sheetId': SHEET_ID, 'dimension': 'COLUMNS', 'startIndex': 1, 'endIndex': 2},
        'properties': {'pixelSize': 140}, 'fields': 'pixelSize'
    }},
    # URL
    {'updateDimensionProperties': {
        'range': {'sheetId': SHEET_ID, 'dimension': 'COLUMNS', 'startIndex': 2, 'endIndex': 3},
        'properties': {'pixelSize': 180}, 'fields': 'pixelSize'
    }},
    # Content columns (D-H)
    {'updateDimensionProperties': {
        'range': {'sheetId': SHEET_ID, 'dimension': 'COLUMNS', 'startIndex': 3, 'endIndex': 8},
        'properties': {'pixelSize': 170}, 'fields': 'pixelSize'
    }},
    # Social columns (I-L)
    {'updateDimensionProperties': {
        'range': {'sheetId': SHEET_ID, 'dimension': 'COLUMNS', 'startIndex': 8, 'endIndex': 12},
        'properties': {'pixelSize': 150}, 'fields': 'pixelSize'
    }},
    # Count column (M)
    {'updateDimensionProperties': {
        'range': {'sheetId': SHEET_ID, 'dimension': 'COLUMNS', 'startIndex': 12, 'endIndex': 13},
        'properties': {'pixelSize': 100}, 'fields': 'pixelSize'
    }},
    # Feedback columns (N-O)
    {'updateDimensionProperties': {
        'range': {'sheetId': SHEET_ID, 'dimension': 'COLUMNS', 'startIndex': 13, 'endIndex': 15},
        'properties': {'pixelSize': 180}, 'fields': 'pixelSize'
    }},
    # AI Summary (P)
    {'updateDimensionProperties': {
        'range': {'sheetId': SHEET_ID, 'dimension': 'COLUMNS', 'startIndex': 15, 'endIndex': 16},
        'properties': {'pixelSize': 280}, 'fields': 'pixelSize'
    }},
    # isNewEntry (Q)
    {'updateDimensionProperties': {
        'range': {'sheetId': SHEET_ID, 'dimension': 'COLUMNS', 'startIndex': 16, 'endIndex': 17},
        'properties': {'pixelSize': 80}, 'fields': 'pixelSize'
    }},

    # 3. Header row height
    {'updateDimensionProperties': {
        'range': {'sheetId': SHEET_ID, 'dimension': 'ROWS', 'startIndex': 0, 'endIndex': 1},
        'properties': {'pixelSize': 45}, 'fields': 'pixelSize'
    }},

    # 4. Format header - Basic info (A-C) - Dark navy
    {'repeatCell': {
        'range': {'sheetId': SHEET_ID, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 3},
        'cell': {
            'userEnteredFormat': {
                'backgroundColor': CAT_BASIC,
                'textFormat': {'foregroundColor': HEADER_TEXT, 'bold': True, 'fontSize': 10, 'fontFamily': 'Roboto'},
                'horizontalAlignment': 'CENTER',
                'verticalAlignment': 'MIDDLE',
                'wrapStrategy': 'WRAP'
            }
        },
        'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)'
    }},

    # 5. Format header - Content (D-H) - Teal
    {'repeatCell': {
        'range': {'sheetId': SHEET_ID, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 3, 'endColumnIndex': 8},
        'cell': {
            'userEnteredFormat': {
                'backgroundColor': CAT_CONTENT,
                'textFormat': {'foregroundColor': HEADER_TEXT, 'bold': True, 'fontSize': 10, 'fontFamily': 'Roboto'},
                'horizontalAlignment': 'CENTER',
                'verticalAlignment': 'MIDDLE',
                'wrapStrategy': 'WRAP'
            }
        },
        'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)'
    }},

    # 6. Format header - Social (I-M) - Green
    {'repeatCell': {
        'range': {'sheetId': SHEET_ID, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 8, 'endColumnIndex': 13},
        'cell': {
            'userEnteredFormat': {
                'backgroundColor': CAT_SOCIAL,
                'textFormat': {'foregroundColor': HEADER_TEXT, 'bold': True, 'fontSize': 10, 'fontFamily': 'Roboto'},
                'horizontalAlignment': 'CENTER',
                'verticalAlignment': 'MIDDLE',
                'wrapStrategy': 'WRAP'
            }
        },
        'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)'
    }},

    # 7. Format header - Feedback (N-O) - Orange
    {'repeatCell': {
        'range': {'sheetId': SHEET_ID, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 13, 'endColumnIndex': 15},
        'cell': {
            'userEnteredFormat': {
                'backgroundColor': CAT_FEEDBACK,
                'textFormat': {'foregroundColor': HEADER_TEXT, 'bold': True, 'fontSize': 10, 'fontFamily': 'Roboto'},
                'horizontalAlignment': 'CENTER',
                'verticalAlignment': 'MIDDLE',
                'wrapStrategy': 'WRAP'
            }
        },
        'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)'
    }},

    # 8. Format header - AI (P-Q) - Purple
    {'repeatCell': {
        'range': {'sheetId': SHEET_ID, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 15, 'endColumnIndex': 17},
        'cell': {
            'userEnteredFormat': {
                'backgroundColor': CAT_AI,
                'textFormat': {'foregroundColor': HEADER_TEXT, 'bold': True, 'fontSize': 10, 'fontFamily': 'Roboto'},
                'horizontalAlignment': 'CENTER',
                'verticalAlignment': 'MIDDLE',
                'wrapStrategy': 'WRAP'
            }
        },
        'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)'
    }},

    # 9. Add thick bottom border to header
    {'updateBorders': {
        'range': {'sheetId': SHEET_ID, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 17},
        'bottom': {'style': 'SOLID_MEDIUM', 'color': {'red': 0.2, 'green': 0.2, 'blue': 0.2}}
    }},

    # 10. Alternating row colors (banding)
    {'addBanding': {
        'bandedRange': {
            'range': {'sheetId': SHEET_ID, 'startRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 17},
            'rowProperties': {
                'firstBandColor': ROW_ALT_2,
                'secondBandColor': ROW_ALT_1
            }
        }
    }},

    # 11. Format data cells - wrap text and vertical align
    {'repeatCell': {
        'range': {'sheetId': SHEET_ID, 'startRowIndex': 1, 'endRowIndex': 1000, 'startColumnIndex': 0, 'endColumnIndex': 17},
        'cell': {
            'userEnteredFormat': {
                'verticalAlignment': 'TOP',
                'wrapStrategy': 'WRAP',
                'textFormat': {'fontSize': 10, 'fontFamily': 'Roboto'}
            }
        },
        'fields': 'userEnteredFormat(verticalAlignment,wrapStrategy,textFormat)'
    }},

    # 12. Center date column (A)
    {'repeatCell': {
        'range': {'sheetId': SHEET_ID, 'startRowIndex': 1, 'endRowIndex': 1000, 'startColumnIndex': 0, 'endColumnIndex': 1},
        'cell': {
            'userEnteredFormat': {
                'horizontalAlignment': 'CENTER'
            }
        },
        'fields': 'userEnteredFormat.horizontalAlignment'
    }},

    # 13. Center count column (M)
    {'repeatCell': {
        'range': {'sheetId': SHEET_ID, 'startRowIndex': 1, 'endRowIndex': 1000, 'startColumnIndex': 12, 'endColumnIndex': 13},
        'cell': {
            'userEnteredFormat': {
                'horizontalAlignment': 'CENTER',
                'textFormat': {'bold': True}
            }
        },
        'fields': 'userEnteredFormat(horizontalAlignment,textFormat.bold)'
    }},

    # 14. Center isNewEntry column (Q)
    {'repeatCell': {
        'range': {'sheetId': SHEET_ID, 'startRowIndex': 1, 'endRowIndex': 1000, 'startColumnIndex': 16, 'endColumnIndex': 17},
        'cell': {
            'userEnteredFormat': {
                'horizontalAlignment': 'CENTER'
            }
        },
        'fields': 'userEnteredFormat.horizontalAlignment'
    }},

    # 15. Add light vertical borders between category groups
    {'updateBorders': {
        'range': {'sheetId': SHEET_ID, 'startRowIndex': 0, 'endRowIndex': 1000, 'startColumnIndex': 2, 'endColumnIndex': 3},
        'right': {'style': 'SOLID', 'color': {'red': 0.8, 'green': 0.8, 'blue': 0.8}}
    }},
    {'updateBorders': {
        'range': {'sheetId': SHEET_ID, 'startRowIndex': 0, 'endRowIndex': 1000, 'startColumnIndex': 7, 'endColumnIndex': 8},
        'right': {'style': 'SOLID', 'color': {'red': 0.8, 'green': 0.8, 'blue': 0.8}}
    }},
    {'updateBorders': {
        'range': {'sheetId': SHEET_ID, 'startRowIndex': 0, 'endRowIndex': 1000, 'startColumnIndex': 12, 'endColumnIndex': 13},
        'right': {'style': 'SOLID', 'color': {'red': 0.8, 'green': 0.8, 'blue': 0.8}}
    }},
    {'updateBorders': {
        'range': {'sheetId': SHEET_ID, 'startRowIndex': 0, 'endRowIndex': 1000, 'startColumnIndex': 14, 'endColumnIndex': 15},
        'right': {'style': 'SOLID', 'color': {'red': 0.8, 'green': 0.8, 'blue': 0.8}}
    }},
]

# Add conditional formatting for isNewEntry = TRUE (highlight row)
requests.append({
    'addConditionalFormatRule': {
        'rule': {
            'ranges': [{'sheetId': SHEET_ID, 'startRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 17}],
            'booleanRule': {
                'condition': {
                    'type': 'CUSTOM_FORMULA',
                    'values': [{'userEnteredValue': '=$Q2=TRUE'}]
                },
                'format': {
                    'backgroundColor': {'red': 1, 'green': 0.95, 'blue': 0.8}  # Light yellow for new entries
                }
            }
        },
        'index': 0
    }
})

result = service.spreadsheets().batchUpdate(
    spreadsheetId=SPREADSHEET_ID,
    body={'requests': requests}
).execute()

print('Formatting applied successfully!')
print(f"Total updates: {len(result.get('replies', []))}")


