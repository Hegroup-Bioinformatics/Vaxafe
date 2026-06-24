import csv
import os

# --- CONFIGURATION ---
INPUT_FILE = "t_vaccine_import_ready.csv"  # Updated to your new file
OUTPUT_FILE = "bulk_upload.sql"            
USER_EMAIL = "admin@violin.com"            
STARTING_ID = 6831                       # CHANGE THIS to your actual MAX(ID) + 1

def escape_sql(val):
    if val is None: return ""
    # Safely escape single quotes and backslashes for MySQL/MariaDB
    return str(val).replace("'", "''").replace("\\", "\\\\")

def main():
    print(f"--- Starting SQL Generation ---")
    print(f"Reading from: {INPUT_FILE}")
    print(f"Auto-generating IDs starting from: {STARTING_ID}")

    try:
        with open(INPUT_FILE, mode='r', encoding='utf-8-sig') as csv_file:
            reader = csv.DictReader(csv_file)
            
            with open(OUTPUT_FILE, mode='w', encoding='utf-8') as sql_file:
                sql_file.write("START TRANSACTION;\n")
                sql_file.write("-- Bulk Upload Script Generated for VIOLIN Database\n\n")

                count = 0
                current_id = STARTING_ID
                
                for row in reader:
                    # 1. ID Logic: Safely handle our temporary 'GEN_xxxx' IDs
                    csv_id = row.get('c_vaccine_id', '').strip()
                    
                    if csv_id.isdigit():
                        vaccine_id = int(csv_id)
                    else:
                        vaccine_id = current_id
                        current_id += 1 

                    # 2. Cleanup (Prevents duplicates/collisions if you re-run the SQL)
                    sql_file.write(f"-- Processing Vaccine ID {vaccine_id} ({row.get('c_vaccine_name', 'Unknown')})\n")
                    sql_file.write(f"DELETE FROM t_revision WHERE c_table_name = 't_vaccine' AND c_record_id = {vaccine_id};\n")
                    sql_file.write(f"DELETE FROM t_record_revision WHERE c_table_name = 't_vaccine' AND c_record_id = {vaccine_id};\n")
                    sql_file.write(f"DELETE FROM t_vaccine WHERE c_vaccine_id = {vaccine_id};\n")

                    # 3. Prepare Variables for t_vaccine
                    cols_main = ['c_vaccine_id']
                    vals_main = [str(vaccine_id)]
                    revision_inserts = []

                    # 4. Record Status (t_record_revision)
                    record_rev_sql = f"""INSERT INTO t_record_revision 
(c_table_name, c_record_id, c_operation, c_submitted_by, c_timestamp, c_comment, c_is_reviewed, c_review_time, c_reviewed_by) 
VALUES 
('t_vaccine', {vaccine_id}, 0, '{USER_EMAIL}', NOW(), 'Bulk Generic Upload', 1, NOW(), '{USER_EMAIL}');\n"""
                    
                    # 5. Loop Columns and build queries
                    for col_name, value in row.items():
                        value = str(value).strip() if value else ""
                        
                        # Skip empty values and excluded columns
                        if value != "" and value.lower() != "nan" and col_name not in ['c_vaccine_id', 'c_full_text', 'c_preparation_vo_id', 'c_cvx_code', 'c_cvx_desc']:
                            clean_val = escape_sql(value)
                            
                            # Add to Main Table arrays
                            cols_main.append(col_name)
                            vals_main.append(f"'{clean_val}'")
                            
                            # Add to Cell-level Revision History (t_revision)
                            rev_sql = f"""INSERT INTO t_revision 
(c_table_name, c_record_id, c_column_name, c_text, c_submitted_by, c_timestamp, c_is_reviewed, c_review_time, c_reviewed_by, c_comment) 
VALUES 
('t_vaccine', {vaccine_id}, '{col_name}', '{clean_val}', '{USER_EMAIL}', NOW(), 1, NOW(), '{USER_EMAIL}', 'Bulk Generic Upload');\n"""
                            revision_inserts.append(rev_sql)

                    # 6. Write to File
                    sql_main = f"INSERT INTO t_vaccine ({', '.join(cols_main)}) VALUES ({', '.join(vals_main)});\n"
                    
                    sql_file.write(sql_main)
                    sql_file.write(record_rev_sql)
                    
                    for sql in revision_inserts:
                        sql_file.write(sql)
                    
                    sql_file.write("\n") 
                    count += 1
                
                sql_file.write("COMMIT;\n")
                
                print(f"\n✅ Success! Processed {count} generic vaccine records.")
                print(f"Ids generated from {STARTING_ID} to {current_id - 1}")
                print(f"SQL file generated: {OUTPUT_FILE}")

    except FileNotFoundError:
        print(f"Error: Could not find '{INPUT_FILE}'. Make sure the script and CSV are in the same folder.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()