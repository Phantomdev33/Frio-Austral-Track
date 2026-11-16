-- Esquema final de referencia. Sin datos. Para ejecutar Django, utilizar manage.py migrate.
PRAGMA foreign_keys=ON;
BEGIN;
CREATE TABLE "auth_group" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(150) NOT NULL UNIQUE);

CREATE TABLE "auth_group_permissions" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "group_id" integer NOT NULL REFERENCES "auth_group" ("id") DEFERRABLE INITIALLY DEFERRED, "permission_id" integer NOT NULL REFERENCES "auth_permission" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "auth_permission" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "content_type_id" integer NOT NULL REFERENCES "django_content_type" ("id") DEFERRABLE INITIALLY DEFERRED, "codename" varchar(100) NOT NULL, "name" varchar(255) NOT NULL);

CREATE TABLE "auth_user" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "password" varchar(128) NOT NULL, "last_login" datetime NULL, "is_superuser" bool NOT NULL, "username" varchar(150) NOT NULL UNIQUE, "last_name" varchar(150) NOT NULL, "email" varchar(254) NOT NULL, "is_staff" bool NOT NULL, "is_active" bool NOT NULL, "date_joined" datetime NOT NULL, "first_name" varchar(150) NOT NULL);

CREATE TABLE "auth_user_groups" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "group_id" integer NOT NULL REFERENCES "auth_group" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "auth_user_user_permissions" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "permission_id" integer NOT NULL REFERENCES "auth_permission" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "django_admin_log" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "object_id" text NULL, "object_repr" varchar(200) NOT NULL, "action_flag" smallint unsigned NOT NULL CHECK ("action_flag" >= 0), "change_message" text NOT NULL, "content_type_id" integer NULL REFERENCES "django_content_type" ("id") DEFERRABLE INITIALLY DEFERRED, "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "action_time" datetime NOT NULL);

CREATE TABLE "django_content_type" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "app_label" varchar(100) NOT NULL, "model" varchar(100) NOT NULL);

CREATE TABLE "django_migrations" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "app" varchar(255) NOT NULL, "name" varchar(255) NOT NULL, "applied" datetime NOT NULL);

CREATE TABLE "django_session" ("session_key" varchar(40) NOT NULL PRIMARY KEY, "session_data" text NOT NULL, "expire_date" datetime NOT NULL);

CREATE TABLE "tracking_alert" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "kind" varchar(20) NOT NULL, "started_at" datetime NOT NULL, "created_at" datetime NOT NULL, "acknowledged" bool NOT NULL, "emailed" bool NOT NULL, "trip_id" bigint NOT NULL REFERENCES "tracking_trip" ("id") DEFERRABLE INITIALLY DEFERRED, "last_observed_at" datetime NULL, "superseded" bool NOT NULL, "triggered_at" datetime NULL, CONSTRAINT "unique_thermal_episode" UNIQUE ("trip_id", "kind", "started_at"));

CREATE TABLE "tracking_delivery" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "customer" varchar(120) NOT NULL, "address" varchar(200) NOT NULL, "window" varchar(40) NOT NULL, "cargo" varchar(160) NOT NULL, "guide" varchar(20) NOT NULL, "priority" integer unsigned NOT NULL CHECK ("priority" >= 0), "position" integer unsigned NOT NULL CHECK ("position" >= 0), "state" varchar(16) NOT NULL, "notes" text NOT NULL, "rejection_reason" text NOT NULL, "photo" varchar(100) NOT NULL, "completed_at" datetime NULL, "certificate_sent" bool NOT NULL, "client_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "trip_id" bigint NOT NULL REFERENCES "tracking_trip" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "tracking_incident" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "event_id" char(32) NOT NULL UNIQUE, "description" text NOT NULL, "assistance" bool NOT NULL, "created_at" datetime NOT NULL, "truck_id" bigint NOT NULL REFERENCES "tracking_truck" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "tracking_order" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "event_id" char(32) NOT NULL UNIQUE, "recipient" varchar(120) NOT NULL, "address" varchar(240) NOT NULL, "branch" varchar(40) NOT NULL, "urgent" bool NOT NULL, "notes" text NOT NULL, "total" integer unsigned NOT NULL CHECK ("total" >= 0), "state" varchar(16) NOT NULL, "created_at" datetime NOT NULL, "client_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "delivery_id" bigint NULL UNIQUE REFERENCES "tracking_delivery" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "tracking_orderitem" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(120) NOT NULL, "unit_price" integer unsigned NOT NULL CHECK ("unit_price" >= 0), "quantity" integer unsigned NOT NULL CHECK ("quantity" >= 0), "order_id" bigint NOT NULL REFERENCES "tracking_order" ("id") DEFERRABLE INITIALLY DEFERRED, "product_id" bigint NOT NULL REFERENCES "tracking_product" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "unique_order_product" UNIQUE ("order_id", "product_id"), CONSTRAINT "positive_order_quantity" CHECK ("quantity" >= 1));

CREATE TABLE "tracking_payment" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "event_id" char(32) NOT NULL UNIQUE, "outcome" varchar(12) NOT NULL, "amount" integer unsigned NOT NULL CHECK ("amount" >= 0), "created_at" datetime NOT NULL, "order_id" bigint NOT NULL REFERENCES "tracking_order" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "tracking_product" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(120) NOT NULL, "description" varchar(240) NOT NULL, "category" varchar(40) NOT NULL, "unit" varchar(30) NOT NULL, "price" integer unsigned NOT NULL CHECK ("price" >= 0), "stock" integer unsigned NOT NULL CHECK ("stock" >= 0), "active" bool NOT NULL);

CREATE TABLE "tracking_profile" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "role" varchar(16) NOT NULL, "user_id" integer NOT NULL UNIQUE REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "tracking_reading" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "event_id" char(32) NOT NULL UNIQUE, "temperature" real NOT NULL, "captured_at" datetime NOT NULL, "received_at" datetime NOT NULL, "trip_id" bigint NOT NULL REFERENCES "tracking_trip" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "tracking_receipt" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "event_id" char(32) NOT NULL UNIQUE, "created_at" datetime NOT NULL, "delivery_id" bigint NOT NULL REFERENCES "tracking_delivery" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "tracking_trip" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "date" date NOT NULL, "truck_id" bigint NOT NULL REFERENCES "tracking_truck" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "tracking_truck" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "code" varchar(12) NOT NULL UNIQUE, "plate" varchar(10) NOT NULL, "branch" varchar(40) NOT NULL, "latitude" text NOT NULL, "online" bool NOT NULL, "last_seen" datetime NULL, "driver_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "longitude" text NOT NULL);

CREATE INDEX "auth_group_permissions_group_id_b120cbf9" ON "auth_group_permissions" ("group_id");

CREATE UNIQUE INDEX "auth_group_permissions_group_id_permission_id_0cd325b0_uniq" ON "auth_group_permissions" ("group_id", "permission_id");

CREATE INDEX "auth_group_permissions_permission_id_84c5c92e" ON "auth_group_permissions" ("permission_id");

CREATE INDEX "auth_permission_content_type_id_2f476e4b" ON "auth_permission" ("content_type_id");

CREATE UNIQUE INDEX "auth_permission_content_type_id_codename_01ab375a_uniq" ON "auth_permission" ("content_type_id", "codename");

CREATE INDEX "auth_user_groups_group_id_97559544" ON "auth_user_groups" ("group_id");

CREATE INDEX "auth_user_groups_user_id_6a12ed8b" ON "auth_user_groups" ("user_id");

CREATE UNIQUE INDEX "auth_user_groups_user_id_group_id_94350c0c_uniq" ON "auth_user_groups" ("user_id", "group_id");

CREATE INDEX "auth_user_user_permissions_permission_id_1fbb5f2c" ON "auth_user_user_permissions" ("permission_id");

CREATE INDEX "auth_user_user_permissions_user_id_a95ead1b" ON "auth_user_user_permissions" ("user_id");

CREATE UNIQUE INDEX "auth_user_user_permissions_user_id_permission_id_14a6b632_uniq" ON "auth_user_user_permissions" ("user_id", "permission_id");

CREATE INDEX "django_admin_log_content_type_id_c4bce8eb" ON "django_admin_log" ("content_type_id");

CREATE INDEX "django_admin_log_user_id_c564eba6" ON "django_admin_log" ("user_id");

CREATE UNIQUE INDEX "django_content_type_app_label_model_76bd3d3b_uniq" ON "django_content_type" ("app_label", "model");

CREATE INDEX "django_session_expire_date_a5c62663" ON "django_session" ("expire_date");

CREATE INDEX "tracking_alert_trip_id_f9449c1b" ON "tracking_alert" ("trip_id");

CREATE INDEX "tracking_delivery_client_id_20e66094" ON "tracking_delivery" ("client_id");

CREATE INDEX "tracking_delivery_trip_id_34da50b3" ON "tracking_delivery" ("trip_id");

CREATE INDEX "tracking_incident_truck_id_d9173356" ON "tracking_incident" ("truck_id");

CREATE INDEX "tracking_order_client_id_1a4cd52d" ON "tracking_order" ("client_id");

CREATE INDEX "tracking_orderitem_order_id_7d95e409" ON "tracking_orderitem" ("order_id");

CREATE INDEX "tracking_orderitem_product_id_f0482531" ON "tracking_orderitem" ("product_id");

CREATE INDEX "tracking_payment_order_id_f126dd12" ON "tracking_payment" ("order_id");

CREATE INDEX "tracking_reading_trip_id_9ebeb0bf" ON "tracking_reading" ("trip_id");

CREATE INDEX "tracking_receipt_delivery_id_3174d02c" ON "tracking_receipt" ("delivery_id");

CREATE INDEX "tracking_trip_truck_id_610e63c2" ON "tracking_trip" ("truck_id");

CREATE INDEX "tracking_truck_driver_id_4fcb3ad1" ON "tracking_truck" ("driver_id");
COMMIT;
