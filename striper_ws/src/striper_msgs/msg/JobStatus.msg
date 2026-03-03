string job_id
uint8 state
float32 progress
uint32 current_segment
uint32 total_segments
string status_message

uint8 IDLE=0
uint8 RUNNING=1
uint8 PAUSED=2
uint8 COMPLETE=3
uint8 ERROR=4
