"""
arcgis_verify_csv_points.py

Script to automate the workflow you requested (ArcPy / ArcGIS Pro).

Inputs (script-tool parameters):
  0) Input CSV table (with latitude/longitude fields)
  1) X field name (longitude)  -- e.g. "X" or "lon" or "Longitude"
  2) Y field name (latitude)   -- e.g. "Y" or "lat" or "Latitude"
  3) Polygon feature class / shapefile (area)
  4) Output folder (folder where shapefiles will be created)
  5) Export outside points to CSV? (Boolean) - default = True

Outputs (created in output folder):
  - points.shp                (all points converted from CSV)
  - points_inside.shp        (points that fall inside polygon)
  - points_spatialjoin.shp   (points_inside with polygon attributes attached)
  - points_outside.shp       (points outside the polygon)
  - points_outside.csv       (optional CSV export of outside points)

Notes:
 - The script assumes coordinates are geographic (lat/long) and uses WGS84 (EPSG:4326).
 - Make sure X field is longitude and Y field is latitude. If your CSV has columns named (lat,lon) you must swap them
   when you set the parameters (X field = lon, Y field = lat).
 - Shapefile names must be <= 13 characters and cannot contain some special characters.

Usage:
 - Best used as a Script Tool in ArcGIS Pro (add this .py as a script tool and define the parameters). Or run inside the ArcGIS Pro Python window after editing the parameters.

Author: generated for user
"""

import arcpy
import os
import csv

arcpy.env.overwriteOutput = True


def export_featureclass_to_csv(feature_class, csv_path):
    """Export attribute table of a feature class to CSV (preserves attribute fields, skips geometry)."""
    # collect field names (skip geometry & OID)
    fields = [f.name for f in arcpy.ListFields(feature_class) if f.type not in ("Geometry", "OID")]
    # write header + rows
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(fields)
        with arcpy.da.SearchCursor(feature_class, fields) as cursor:
            for row in cursor:
                writer.writerow(list(row))


def main():
    try:
        # --- parameters (when used as ArcGIS Script Tool these come from the tool dialog) ---
        in_csv = arcpy.GetParameterAsText(0)           # path to CSV (or table)
        x_field = arcpy.GetParameterAsText(1)         # name of X field (longitude)
        y_field = arcpy.GetParameterAsText(2)         # name of Y field (latitude)
        polygon_fc = arcpy.GetParameterAsText(3)     # polygon shapefile / fc
        out_folder = arcpy.GetParameterAsText(4)     # output folder for shapefiles
        export_csv_param = arcpy.GetParameterAsText(5)

        # default for export flag
        export_csv = True
        if export_csv_param:
            if export_csv_param.strip().lower() in ("false", "no", "0"):
                export_csv = False

        # --- basic checks ---
        if not arcpy.Exists(in_csv):
            arcpy.AddError(f"Input CSV/table not found: {in_csv}")
            return
        if not arcpy.Exists(polygon_fc):
            arcpy.AddError(f"Polygon feature not found: {polygon_fc}")
            return
        if not out_folder:
            arcpy.AddError("Please provide an output folder path.")
            return
        if not os.path.isdir(out_folder):
            os.makedirs(out_folder)

        # --- output paths (shapefile names) ---
        points_shp = os.path.join(out_folder, "points.shp")
        inside_shp = os.path.join(out_folder, "points_inside.shp")
        join_shp = os.path.join(out_folder, "points_spatialjoin.shp")
        outside_shp = os.path.join(out_folder, "points_outside.shp")
        outside_csv = os.path.join(out_folder, "points_outside.csv")

        arcpy.AddMessage("\n=== START: CSV -> points (WGS84) ===")

        # --- 1) convert CSV to point shapefile (WGS84) ---
        arcpy.AddMessage("1) Converting CSV to point shapefile (XYTableToPoint) ...")
        spatial_ref = arcpy.SpatialReference(4326)  # WGS84 lat/long
        # XYTableToPoint will create point features using X_field (longitude) and Y_field (latitude)
        arcpy.management.XYTableToPoint(in_table=in_csv, out_feature_class=points_shp,
                                        x_field=x_field, y_field=y_field, coordinate_system=spatial_ref)
        if not arcpy.Exists(points_shp):
            arcpy.AddError("Failed to create points shapefile. Check field names and CSV format.")
            return
        arcpy.AddMessage(f" - Points shapefile created: {points_shp}")

        # --- 2) make feature layers for selection ---
        arcpy.AddMessage("2) Creating feature layers for selection...")
        arcpy.management.MakeFeatureLayer(points_shp, "points_lyr")
        arcpy.management.MakeFeatureLayer(polygon_fc, "poly_lyr")

        # --- 3) select points inside polygon and export ---
        arcpy.AddMessage("3) Selecting points INSIDE polygon...")
        arcpy.management.SelectLayerByLocation("points_lyr", "INTERSECT", "poly_lyr", "", "NEW_SELECTION")
        count_inside = int(arcpy.management.GetCount("points_lyr").getOutput(0))
        if count_inside > 0:
            arcpy.management.CopyFeatures("points_lyr", inside_shp)
            arcpy.AddMessage(f" - {count_inside} points inside -> saved to: {inside_shp}")

            # spatial join: attach polygon attributes to the inside points
            arcpy.AddMessage("4) Performing spatial join (attach polygon attributes to points inside)...")
            arcpy.analysis.SpatialJoin(target_features=inside_shp, join_features=polygon_fc, out_feature_class=join_shp)
            arcpy.AddMessage(f" - Spatial join output: {join_shp}")
        else:
            arcpy.AddMessage(" - No points were found inside the polygon. Skipping inside/shapjoin outputs.")
            if arcpy.Exists(inside_shp):
                arcpy.management.Delete(inside_shp)

        # --- 5) select points outside polygon and export ---
        arcpy.AddMessage("5) Selecting points OUTSIDE polygon (inverse selection)...")
        arcpy.management.SelectLayerByLocation("points_lyr", "INTERSECT", "poly_lyr", "", "NEW_SELECTION", "INVERT")
        count_outside = int(arcpy.management.GetCount("points_lyr").getOutput(0))
        if count_outside > 0:
            arcpy.management.CopyFeatures("points_lyr", outside_shp)
            arcpy.AddMessage(f" - {count_outside} points outside -> saved to: {outside_shp}")

            # optional: export outside points to CSV (Excel can open it)
            if export_csv:
                arcpy.AddMessage("6) Exporting outside points attribute table to CSV...")
                export_featureclass_to_csv(outside_shp, outside_csv)
                arcpy.AddMessage(f" - CSV exported: {outside_csv}")
        else:
            arcpy.AddMessage(" - No points outside polygon.")
            if arcpy.Exists(outside_shp):
                arcpy.management.Delete(outside_shp)

        arcpy.AddMessage("\n=== PROCESS COMPLETED ===")

    except Exception as ex:
        arcpy.AddError(f"Script failed: {ex}")
        raise


if __name__ == '__main__':
    main()
