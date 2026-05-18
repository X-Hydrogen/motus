#!/usr/bin/env vmd -dispdev text -e
# ============================================================
# vmd_rdf.tcl — Fast RDF via VMD measure gofr for large systems
# MOTUS v1.0 — replaces O(N²) rdf_gen.py for >5000 atom systems
#
# Usage (called from bash):
#   vmd -dispdev text -e vmd_rdf.tcl -args CMS_FILE TRJ_DIR OUTDIR STRIDE ELEMENTS
#
# VMD's measure gofr uses multi-threaded C implementation with
# spatial indexing — 100-1000× faster than pure Python O(N²).
# ============================================================

# Parse arguments
if {[llength $argv] < 3} {
    puts "Usage: vmd -dispdev text -e vmd_rdf.tcl -args CMS TRJ_DIR OUTDIR [STRIDE] [ELEMENTS]"
    exit 1
}

set cms_file [lindex $argv 0]
set trj_dir  [lindex $argv 1]
set outdir   [lindex $argv 2]
set stride   [expr {[llength $argv] > 3 ? [lindex $argv 3] : 10}]
set r_max    15.0
set delta    0.1
set nbins    [expr {int($r_max / $delta)}]

# ── Load system ──
puts "📊 VMD RDF Generator (fast, multi-threaded)"
puts "   CMS: $cms_file"
puts "   TRJ: $trj_dir"
puts "   Stride: $stride"

mol new $cms_file
mol addfile $trj_dir type dtr first 0 last -1 step $stride waitfor all

set n_frames [molinfo top get numframes]
set n_atoms  [molinfo top get numatoms]
puts "   Atoms: $n_atoms  Frames: $n_frames"

# ── Discover elements ──
set sel_all [atomselect top all]
array set element_counts {}
foreach el [$sel_all get element] {
    if {[info exists element_counts($el)]} {
        incr element_counts($el)
    } else {
        set element_counts($el) 1
    }
}
$sel_all delete

# Sort elements by abundance, include all non-trivial ones
set elements [lsort [array names element_counts]]
puts "   Elements: $elements"
foreach el $elements {
    puts "     $el: $element_counts($el)"
}

# Filter out rare/trace elements (< 10 atoms)
set significant_elements {}
foreach el $elements {
    if {$element_counts($el) >= 3} {
        lappend significant_elements $el
    }
}
puts "   Significant elements (>=3 atoms): $significant_elements"

# ── Compute element-pair RDFs ──
set n_pairs 0
set npairs [llength $significant_elements]

for {set i 0} {$i < $npairs} {incr i} {
    for {set j $i} {$j < $npairs} {incr j} {
        set e1 [lindex $significant_elements $i]
        set e2 [lindex $significant_elements $j]
        
        # Build selection strings
        set sel1_text "element $e1"
        set sel2_text "element $e2"
        
        # Create selections
        set sel1 [atomselect top $sel1_text]
        set sel2 [atomselect top $sel2_text]
        
        set n1 [$sel1 num]
        set n2 [$sel2 num]
        
        if {$n1 == 0 || $n2 == 0} {
            $sel1 delete; $sel2 delete
            continue
        }
        
        set pair_name "${e1}_${e2}"
        puts -nonewline "   \[[expr {$n_pairs + 1}]\] $pair_name ($n1 × $n2 atoms)... "
        flush stdout
        
        # Compute g(r) — selupdate 1 means reselect atoms each frame
        # Returns: {r_list g_list n_r_list}
        set t_start [clock milliseconds]
        set result [measure gofr $sel1 $sel2 \
            delta $delta rmax $r_max \
            usepbc 1 selupdate 1]
        set t_elapsed [expr {[clock milliseconds] - $t_start}]
        
        set r_list  [lindex $result 0]
        set g_list  [lindex $result 1]
        set n_list  [lindex $result 2]
        
        # Write CSV
        set csv_path [file join $outdir "rdf_element_${pair_name}.csv"]
        set fh [open $csv_path w]
        puts $fh "r_A,g_r,n_r"
        set n_bins [llength $r_list]
        for {set k 0} {$k < $n_bins} {incr k} {
            set r_val [lindex $r_list $k]
            set g_val [lindex $g_list $k]
            set n_val [lindex $n_list $k]
            puts $fh [format "%.4f,%.6f,%.4f" $r_val $g_val $n_val]
        }
        close $fh
        
        # Find peak
        set peak_g 0
        set peak_r 0
        for {set k 0} {$k < $n_bins} {incr k} {
            set gv [lindex $g_list $k]
            if {$gv > $peak_g} {
                set peak_g $gv
                set peak_r [lindex $r_list $k]
            }
        }
        # Find coordination number at ~first minimum after peak
        set cn_val [lindex $n_list [expr {min($n_bins - 1, int($peak_r / $delta + 10))}]]
        
        puts "✓  g(r_max)=[format %.1f $peak_g] at r=[format %.2f $peak_r]  CN≈[format %.1f $cn_val]  ([expr {$t_elapsed/1000.0}]s)"
        
        $sel1 delete
        $sel2 delete
        incr n_pairs
    }
}

puts "\n✅ VMD RDF: $n_pairs element-pair RDFs saved to $outdir/"
exit
