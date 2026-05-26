import json
import argparse
import sys
import os
from collections import defaultdict

# Selective import of rich for gorgeous console visuals
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.tree import Tree
    from rich.text import Text
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

def print_banner(console):
    if RICH_AVAILABLE:
        console.print(Panel.fit(
            "[bold cyan]▲ COMPILE-TIME STACK USAGE ANALYZER ▲[/bold cyan]\n"
            "[italic white]LLVM-Native High-Fidelity Static Frame Estimation[/italic white]",
            border_style="cyan"
        ))
    else:
        print("==============================================")
        print("▲ COMPILE-TIME STACK USAGE ANALYZER ▲")
        print("==============================================")

def find_sccs(graph):
    """Find Strongly Connected Components (Tarjan's algorithm) to identify recursion."""
    index_counter = [0]
    stack = []
    lowlink = {}
    index = {}
    on_stack = set()
    sccs = []

    def strongconnect(node):
        index[node] = index_counter[0]
        lowlink[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        on_stack.add(node)

        # Get callees
        callees = graph.get(node, {}).get("callees", [])
        for callee in callees:
            if callee not in index:
                strongconnect(callee)
                lowlink[node] = min(lowlink[node], lowlink[callee])
            elif callee in on_stack:
                lowlink[node] = min(lowlink[node], index[callee])

        if lowlink[node] == index[node]:
            scc = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                scc.append(w)
                if w == node:
                    break
            sccs.append(scc)

    for node in graph:
        if node not in index:
            strongconnect(node)
            
    return sccs

def compute_cumulative_stack(node, graph, sizes, visited, memo, recursion_flags, indirect_cost):
    """Propagate worst-case stack usage recursively with dynamic programming and cycle-breaking."""
    if node in memo:
        return memo[node][0]

    if node in visited:
        # Cycle / Recursion detected!
        recursion_flags[node] = True
        return 0

    visited.add(node)
    
    node_size = sizes.get(node, 0)
    max_callee_stack = 0
    best_callee = None

    # Process direct calls
    callees = graph.get(node, {}).get("callees", [])
    for callee in callees:
        callee_stack = compute_cumulative_stack(
            callee, graph, sizes, visited, memo, recursion_flags, indirect_cost
        )
        if callee_stack > max_callee_stack:
            max_callee_stack = callee_stack
            best_callee = callee

    # Process indirect calls if any
    indirects = graph.get(node, {}).get("indirect_calls", [])
    if indirects:
        # Apply the configured indirect call stack penalty
        if indirect_cost > max_callee_stack:
            max_callee_stack = indirect_cost
            # Track as indirect call target signature representation
            best_callee = f"<Indirect: {indirects[0]}>"

    visited.remove(node)
    
    total = node_size + max_callee_stack
    memo[node] = (total, best_callee)
    return total

def reconstruct_path(node, memo):
    path = []
    curr = node
    while curr:
        path.append(curr)
        # Follow the worst-case successor path
        if curr in memo:
            curr = memo[curr][1]
            if curr in path: # Avoid infinite loop in cycle reconstruction
                path.append(f"{curr} (Recursion Loop)")
                break
        else:
            break
    return path

def main():
    parser = argparse.ArgumentParser(description="Static Compile-Time Stack Usage Graph Propagation Solver")
    parser.add_argument("--sizes", default="stack_sizes.json", help="Path to stack_sizes.json")
    parser.add_argument("--cg", default="call_graph.json", help="Path to call_graph.json")
    parser.add_argument("--indirect-cost", type=int, default=256, help="Configurable upper bound stack cost for indirect calls (bytes)")
    parser.add_argument("--threshold", type=int, default=1024, help="Highlight depth exceeding this threshold (bytes)")
    parser.add_argument("--top-n", type=int, default=5, help="Number of deepest call chains to display")
    args = parser.parse_args()

    console = Console() if RICH_AVAILABLE else None
    print_banner(console)

    # Load JSON inputs
    if not os.path.exists(args.sizes) or not os.path.exists(args.cg):
        err_msg = f"Error: Input files '{args.sizes}' or '{args.cg}' not found. Run stack-extractor first."
        if RICH_AVAILABLE:
            console.print(f"[bold red]{err_msg}[/bold red]")
        else:
            print(err_msg)
        sys.exit(1)

    sizes = {}
    if args.sizes.endswith(".su"):
        with open(args.sizes, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split('\t')
                if len(parts) >= 2:
                    func_part = parts[0]
                    try:
                        size_val = int(parts[1])
                    except ValueError:
                        continue
                    func_name = func_part.split(':')[-1]
                    sizes[func_name] = size_val
    else:
        with open(args.sizes, "r") as f:
            sizes = json.load(f)
            
    with open(args.cg, "r") as f:
        graph = json.load(f)

    # Perform Strongly Connected Components detection for recursion checks
    sccs = find_sccs(graph)
    recursive_groups = []
    has_recursion = False
    
    for scc in sccs:
        # An SCC represents recursion if it has size > 1, or size == 1 with a self-loop
        if len(scc) > 1:
            recursive_groups.append(scc)
            has_recursion = True
        elif len(scc) == 1:
            node = scc[0]
            if node in graph.get(node, {}).get("callees", []):
                recursive_groups.append(scc)
                has_recursion = True

    # Propagate and solve stack depths
    memo = {}
    recursion_flags = defaultdict(bool)
    
    # Identify entry points (functions that are never called directly)
    all_callees = set()
    for node, info in graph.items():
        all_callees.update(info.get("callees", []))
    
    entry_points = [node for node in graph if node not in all_callees]
    if not entry_points:
        # Fallback to all functions in case of strongly recursive or cyclic programs
        entry_points = list(graph.keys())

    # Propagate stack sizes
    for entry in entry_points:
        compute_cumulative_stack(entry, graph, sizes, set(), memo, recursion_flags, args.indirect_cost)

    # Format and present results
    if RICH_AVAILABLE:
        # 1. Summary Box
        total_funcs = len(graph)
        max_depth = max([memo[node][0] for node in memo] + [0])
        
        summary_text = (
            f"• [bold]Total Functions Statically Analyzed:[/bold] {total_funcs}\n"
            f"• [bold]Deepest Estimated Stack Path:[/bold] {max_depth} bytes\n"
            f"• [bold]Configured Indirect Call Penalty:[/bold] {args.indirect_cost} bytes\n"
            f"• [bold]Global Overflow Alert Threshold:[/bold] {args.threshold} bytes"
        )
        console.print(Panel(summary_text, title="[bold yellow]Analysis Summary[/bold yellow]", border_style="yellow"))
        console.print()

        # 2. Recursion warnings
        if has_recursion:
            warning_text = ""
            for group in recursive_groups:
                warning_text += f"▲ [bold red]Recursion Loop:[/bold red] {' -> '.join(group)} -> {group[0]}\n"
            console.print(Panel(warning_text.strip(), title="[bold red]⚠️ RECURSION WARNINGS[/bold red]", border_style="red"))
            console.print()

        # 3. Entry Points Table
        table = Table(title="[bold green]Entry Point Cumulative Stack Depths[/bold green]")
        table.add_column("Entry Point / Function Name", style="cyan", no_wrap=True)
        table.add_column("Frame Size (Own)", justify="right", style="magenta")
        table.add_column("Worst-Case Path Depth (Cumulative)", justify="right")
        table.add_column("Status", justify="center")

        for entry in sorted(entry_points, key=lambda x: memo.get(x, (0, None))[0], reverse=True):
            if entry not in memo:
                continue
            cum_stack, _ = memo[entry]
            own_size = sizes.get(entry, 0)
            
            # Formatting status & coloring thresholds
            status = "[green]OK[/green]"
            cum_str = f"[green]{cum_stack} B[/green]"
            if cum_stack >= args.threshold:
                status = "[blink bold red]⚠️ RISK[/blink bold red]"
                cum_str = f"[bold red]{cum_stack} B[/bold red]"
            elif cum_stack >= args.threshold * 0.8:
                status = "[yellow]WARN[/yellow]"
                cum_str = f"[yellow]{cum_stack} B[/yellow]"

            if recursion_flags[entry]:
                status += " [red](Recursive)[/red]"

            table.add_row(entry, f"{own_size} B", cum_str, status)
        
        console.print(table)
        console.print()

        # 4. Top-N Deepest Call Chains
        console.print(f"[bold cyan]Top-{args.top_n} Deepest Statically Estimated Call Chains:[/bold cyan]")
        
        sorted_nodes = sorted(memo.keys(), key=lambda x: memo[x][0], reverse=True)
        displayed = 0
        for node in sorted_nodes:
            if displayed >= args.top_n:
                break
            # Only display paths starting at entry points or deep functions
            path = reconstruct_path(node, memo)
            if len(path) <= 1 and sizes.get(node, 0) == 0:
                continue
                
            cum_stack = memo[node][0]
            
            tree_title = Text.assemble(
                ("Worst-Case Chain from ", "white"),
                (f"{node}", "cyan bold"),
                (f" (Total: {cum_stack} bytes)", "red" if cum_stack >= args.threshold else "green")
            )
            tree = Tree(tree_title)
            
            curr_tree = tree
            for idx, p_node in enumerate(path):
                if p_node.startswith("<Indirect:"):
                    curr_tree.add(f"[italic yellow]↪ {p_node} (+{args.indirect_cost} bytes boundary)[/italic yellow]")
                elif "Recursion Loop" in p_node:
                    curr_tree.add(f"[bold red]↪ ↺ {p_node}[/bold red]")
                else:
                    own_size = sizes.get(p_node, 0)
                    cum_node_size = memo.get(p_node, (0, None))[0]
                    curr_tree = curr_tree.add(f"[bold cyan]↪ {p_node}[/bold cyan] [magenta]({own_size} B frame)[/magenta] [dim green](cum: {cum_node_size} B)[/dim green]")
            
            console.print(tree)
            console.print()
            displayed += 1
    else:
        # Fallback raw presentation
        print("--- Stack Analyzer Propagation Results ---")
        if has_recursion:
            print("WARNING: Recursion detected in target codebase!")
            for group in recursive_groups:
                print(f"  Cycle: {' -> '.join(group)}")
        print("\nFunction Stack Depths:")
        for node, val in sorted(memo.items(), key=lambda x: x[1][0], reverse=True):
            print(f"  {node}: {val[0]} bytes (Frame: {sizes.get(node, 0)} bytes, next: {val[1]})")
            path = reconstruct_path(node, memo)
            print(f"    Path: {' -> '.join(path)}")

if __name__ == "__main__":
    main()
