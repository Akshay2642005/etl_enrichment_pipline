-- Sample PostgreSQL DDL — Airport Turnaround Operations
-- Extracted from raw_metadata.json table definitions

CREATE TABLE departmentsss (
    department_id INTEGER NOT NULL,
    department_name VARCHAR(100) NOT NULL,
    CONSTRAINT department_pkey PRIMARY KEY (department_id)
);

CREATE TABLE employee (
    employee_id INTEGER NOT NULL,
    employee_name VARCHAR(200) NOT NULL,
    department_id INTEGER,
    CONSTRAINT employee_pkey PRIMARY KEY (employee_id),
    CONSTRAINT employee_department_id_fkey FOREIGN KEY (department_id) REFERENCES department(department_id)
);

CREATE TABLE attendance (
    attendance_id INTEGER NOT NULL,
    employee_id INTEGER,
    check_in TIMESTAMP WITHOUT TIME ZONE,
    check_out TIMESTAMP WITHOUT TIME ZONE,
    attendance_date DATE,
    CONSTRAINT attendance_pkey PRIMARY KEY (attendance_id),
    CONSTRAINT attendance_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES employee(employee_id)
);

CREATE TABLE role (
    role_id INTEGER NOT NULL,
    role_name VARCHAR(100) NOT NULL,
    CONSTRAINT role_pkey PRIMARY KEY (role_id)
);

CREATE TABLE employee_role (
    employee_role_id INTEGER NOT NULL,
    employee_id INTEGER,
    role_id INTEGER,
    CONSTRAINT employee_role_pkey PRIMARY KEY (employee_role_id),
    CONSTRAINT employee_role_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES employee(employee_id),
    CONSTRAINT employee_role_role_id_fkey FOREIGN KEY (role_id) REFERENCES role(role_id)
);

CREATE TABLE shift (
    shift_id INTEGER NOT NULL,
    shift_name VARCHAR(50),
    start_time TIME WITHOUT TIME ZONE,
    end_time TIME WITHOUT TIME ZONE,
    CONSTRAINT shift_pkey PRIMARY KEY (shift_id)
);

CREATE TABLE schedule (
    schedule_id INTEGER NOT NULL,
    employee_id INTEGER,
    shift_id INTEGER,
    schedule_date DATE,
    CONSTRAINT schedule_pkey PRIMARY KEY (schedule_id),
    CONSTRAINT schedule_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES employee(employee_id),
    CONSTRAINT schedule_shift_id_fkey FOREIGN KEY (shift_id) REFERENCES shift(shift_id)
);

CREATE TABLE leave_request (
    leave_request_id INTEGER NOT NULL,
    employee_id INTEGER,
    leave_type VARCHAR(50),
    start_date DATE,
    end_date DATE,
    status VARCHAR(50),
    CONSTRAINT leave_request_pkey PRIMARY KEY (leave_request_id),
    CONSTRAINT leave_request_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES employee(employee_id)
);

CREATE TABLE training_record (
    training_id INTEGER NOT NULL,
    employee_id INTEGER,
    training_name VARCHAR(200),
    completion_date DATE,
    CONSTRAINT training_record_pkey PRIMARY KEY (training_id),
    CONSTRAINT training_record_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES employee(employee_id)
);

CREATE TABLE equipment_type (
    equipment_type_id INTEGER NOT NULL,
    type_name VARCHAR(100),
    CONSTRAINT equipment_type_pkey PRIMARY KEY (equipment_type_id)
);

CREATE TABLE equipment (
    equipment_id INTEGER NOT NULL,
    equipment_name VARCHAR(200),
    status VARCHAR(50),
    equipment_type_id INTEGER,
    CONSTRAINT equipment_pkey PRIMARY KEY (equipment_id),
    CONSTRAINT equipment_equipment_type_id_fkey FOREIGN KEY (equipment_type_id) REFERENCES equipment_type(equipment_type_id)
);

CREATE TABLE equipment_assignment (
    assignment_id INTEGER NOT NULL,
    equipment_id INTEGER,
    employee_id INTEGER,
    assigned_date DATE,
    returned_date DATE,
    CONSTRAINT equipment_assignment_pkey PRIMARY KEY (assignment_id),
    CONSTRAINT equipment_assignment_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES equipment(equipment_id),
    CONSTRAINT equipment_assignment_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES employee(employee_id)
);

CREATE TABLE maintenance_request (
    request_id INTEGER NOT NULL,
    equipment_id INTEGER,
    description TEXT,
    status VARCHAR(50),
    CONSTRAINT maintenance_request_pkey PRIMARY KEY (request_id),
    CONSTRAINT maintenance_request_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES equipment(equipment_id)
);

CREATE TABLE maintenance_history (
    maintenance_history_id INTEGER NOT NULL,
    equipment_id INTEGER,
    maintenance_date DATE,
    remarks TEXT,
    CONSTRAINT maintenance_history_pkey PRIMARY KEY (maintenance_history_id),
    CONSTRAINT maintenance_history_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES equipment(equipment_id)
);

CREATE TABLE flight (
    flight_id INTEGER NOT NULL,
    flight_number VARCHAR(20),
    status VARCHAR(50),
    CONSTRAINT flight_pkey PRIMARY KEY (flight_id)
);

CREATE TABLE gate (
    gate_id INTEGER NOT NULL,
    gate_number VARCHAR(10),
    status VARCHAR(50),
    CONSTRAINT gate_pkey PRIMARY KEY (gate_id)
);

CREATE TABLE stand (
    stand_id INTEGER NOT NULL,
    stand_number VARCHAR(10),
    status VARCHAR(50),
    CONSTRAINT stand_pkey PRIMARY KEY (stand_id)
);

CREATE TABLE gate_assignment (
    gate_assignment_id INTEGER NOT NULL,
    gate_id INTEGER,
    flight_id INTEGER,
    assigned_time TIMESTAMP WITHOUT TIME ZONE,
    CONSTRAINT gate_assignment_pkey PRIMARY KEY (gate_assignment_id),
    CONSTRAINT gate_assignment_gate_id_fkey FOREIGN KEY (gate_id) REFERENCES gate(gate_id),
    CONSTRAINT gate_assignment_flight_id_fkey FOREIGN KEY (flight_id) REFERENCES flight(flight_id)
);

CREATE TABLE stand_assignment (
    stand_assignment_id INTEGER NOT NULL,
    stand_id INTEGER,
    flight_id INTEGER,
    assigned_time TIMESTAMP WITHOUT TIME ZONE,
    CONSTRAINT stand_assignment_pkey PRIMARY KEY (stand_assignment_id),
    CONSTRAINT stand_assignment_stand_id_fkey FOREIGN KEY (stand_id) REFERENCES stand(stand_id),
    CONSTRAINT stand_assignment_flight_id_fkey FOREIGN KEY (flight_id) REFERENCES flight(flight_id)
);

CREATE TABLE turnaround_operation (
    turnaround_id INTEGER NOT NULL,
    flight_id INTEGER,
    start_time TIMESTAMP WITHOUT TIME ZONE,
    target_departure_time TIMESTAMP WITHOUT TIME ZONE,
    status VARCHAR(50),
    CONSTRAINT turnaround_operation_pkey PRIMARY KEY (turnaround_id),
    CONSTRAINT turnaround_operation_flight_id_fkey FOREIGN KEY (flight_id) REFERENCES flight(flight_id)
);

CREATE TABLE turnaround_checklist (
    checklist_id INTEGER NOT NULL,
    turnaround_id INTEGER,
    checklist_item VARCHAR(200),
    completed BOOLEAN,
    CONSTRAINT turnaround_checklist_pkey PRIMARY KEY (checklist_id),
    CONSTRAINT turnaround_checklist_turnaround_id_fkey FOREIGN KEY (turnaround_id) REFERENCES turnaround_operation(turnaround_id)
);

CREATE TABLE boarding_task (
    boarding_task_id INTEGER NOT NULL,
    turnaround_id INTEGER,
    gate_ready BOOLEAN,
    baggage_loaded BOOLEAN,
    status VARCHAR(50),
    CONSTRAINT boarding_task_pkey PRIMARY KEY (boarding_task_id),
    CONSTRAINT boarding_task_turnaround_id_fkey FOREIGN KEY (turnaround_id) REFERENCES turnaround_operation(turnaround_id)
);

CREATE TABLE refueling_task (
    refueling_task_id INTEGER NOT NULL,
    turnaround_id INTEGER,
    fuel_remaining NUMERIC,
    fuel_required NUMERIC,
    fuel_added NUMERIC,
    status VARCHAR(50),
    CONSTRAINT refueling_task_pkey PRIMARY KEY (refueling_task_id),
    CONSTRAINT refueling_task_turnaround_id_fkey FOREIGN KEY (turnaround_id) REFERENCES turnaround_operation(turnaround_id)
);

CREATE TABLE catering_task (
    catering_task_id INTEGER NOT NULL,
    turnaround_id INTEGER,
    catering_vendor VARCHAR(100),
    start_time TIMESTAMP WITHOUT TIME ZONE,
    end_time TIMESTAMP WITHOUT TIME ZONE,
    status VARCHAR(50),
    CONSTRAINT catering_task_pkey PRIMARY KEY (catering_task_id),
    CONSTRAINT catering_task_turnaround_id_fkey FOREIGN KEY (turnaround_id) REFERENCES turnaround_operation(turnaround_id)
);

CREATE TABLE cleaning_task (
    cleaning_task_id INTEGER NOT NULL,
    turnaround_id INTEGER,
    assigned_employee_id INTEGER,
    start_time TIMESTAMP WITHOUT TIME ZONE,
    end_time TIMESTAMP WITHOUT TIME ZONE,
    status VARCHAR(50),
    CONSTRAINT cleaning_task_pkey PRIMARY KEY (cleaning_task_id),
    CONSTRAINT cleaning_task_turnaround_id_fkey FOREIGN KEY (turnaround_id) REFERENCES turnaround_operation(turnaround_id),
    CONSTRAINT cleaning_task_assigned_employee_id_fkey FOREIGN KEY (assigned_employee_id) REFERENCES employee(employee_id)
);

CREATE TABLE baggage (
    baggage_id INTEGER NOT NULL,
    flight_id INTEGER,
    tag_number VARCHAR(100),
    status VARCHAR(50),
    CONSTRAINT baggage_pkey PRIMARY KEY (baggage_id),
    CONSTRAINT baggage_flight_id_fkey FOREIGN KEY (flight_id) REFERENCES flight(flight_id)
);

CREATE TABLE baggage_loading (
    loading_id INTEGER NOT NULL,
    baggage_id INTEGER,
    flight_id INTEGER,
    loading_time TIMESTAMP WITHOUT TIME ZONE,
    CONSTRAINT baggage_loading_pkey PRIMARY KEY (loading_id),
    CONSTRAINT baggage_loading_baggage_id_fkey FOREIGN KEY (baggage_id) REFERENCES baggage(baggage_id),
    CONSTRAINT baggage_loading_flight_id_fkey FOREIGN KEY (flight_id) REFERENCES flight(flight_id)
);

CREATE TABLE baggage_unloading (
    unloading_id INTEGER NOT NULL,
    baggage_id INTEGER,
    flight_id INTEGER,
    unloading_time TIMESTAMP WITHOUT TIME ZONE,
    CONSTRAINT baggage_unloading_pkey PRIMARY KEY (unloading_id),
    CONSTRAINT baggage_unloading_baggage_id_fkey FOREIGN KEY (baggage_id) REFERENCES baggage(baggage_id),
    CONSTRAINT baggage_unloading_flight_id_fkey FOREIGN KEY (flight_id) REFERENCES flight(flight_id)
);

CREATE TABLE baggage_scan (
    scan_id INTEGER NOT NULL,
    baggage_id INTEGER,
    scan_location VARCHAR(200),
    scan_time TIMESTAMP WITHOUT TIME ZONE,
    CONSTRAINT baggage_scan_pkey PRIMARY KEY (scan_id),
    CONSTRAINT baggage_scan_baggage_id_fkey FOREIGN KEY (baggage_id) REFERENCES baggage(baggage_id)
);

CREATE TABLE lost_baggage (
    lost_id INTEGER NOT NULL,
    baggage_id INTEGER,
    status VARCHAR(50),
    description TEXT,
    CONSTRAINT lost_baggage_pkey PRIMARY KEY (lost_id),
    CONSTRAINT lost_baggage_baggage_id_fkey FOREIGN KEY (baggage_id) REFERENCES baggage(baggage_id)
);
