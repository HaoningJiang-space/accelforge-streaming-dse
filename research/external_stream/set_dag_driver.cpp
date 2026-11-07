// Exercise the pinned SET layer mapper, complete RA-tree allocator and SA.
#include <cstdlib>
#include <iomanip>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include "cluster.h"
#include "coremapping.h"
#include "layerengine.h"
#include "network.h"
#include "sa.h"
#include "schnode.h"

namespace {
using Type = LTreeNode::NodeType;
constexpr int cores = 6;

Network read_graph() {
    len_t rows, input_width;
    int size;
    if (!(std::cin >> rows >> input_width >> size) || !rows || !input_width || size < 2) {
        throw std::invalid_argument("expected DAG extents and operator count");
    }
    Network result;
    for (int index = 0; index < size; ++index) {
        std::string name, kind;
        len_t width, contraction;
        int first, second;
        if (!(std::cin >> name >> kind >> width >> contraction >> first >> second) ||
            first < -1 || first >= index || second < -1 || second >= index) {
            throw std::invalid_argument("invalid DAG operator");
        }
        if (kind == "gemm" && second == -1) {
            Network::layer_set predecessors;
            std::vector<InputData> external;
            if (first == -1) external.emplace_back("X", fmap_shape(input_width, rows, 1));
            else predecessors.push_back(static_cast<lid_t>(first));
            result.add(NLAYER(name, Conv, C=contraction, K=width, H=rows, W=1, R=1, S=1),
                       predecessors, 8, external);
        } else if ((kind == "add" || kind == "mul") && first >= 0 && second >= 0 && first != second) {
            result.add(NLAYER(name, Eltwise, K=width, H=rows, W=1, N=2),
                       {static_cast<lid_t>(first), static_cast<lid_t>(second)}, 8);
        } else {
            throw std::invalid_argument("unsupported DAG operator");
        }
    }
    return result;
}

void print_tree(LTreeNode& tree) {
    if (tree.get_type() == Type::L) {
        const auto layer = tree.layers().first();
        std::cout << "{\"layer\":" << layer << ",\"drain\":" << tree.get_to_dram() << ",\"direct\":[";
        const auto& direct = tree.get_dirp_set();
        bool first = true;
        FOR_BITSET(pred, direct) {
            if (!first) std::cout << ',';
            std::cout << pred;
            first = false;
        }
        std::cout << "]}";
        return;
    }
    std::cout << "{\"type\":\"" << (tree.get_type() == Type::T ? 'T' : 'S') << "\",\"children\":[";
    bool first = true;
    for (auto child : tree.get_children()) {
        if (!first) std::cout << ',';
        print_tree(*child);
        first = false;
    }
    std::cout << "]}";
}

LTreeNode* read_node(LTreeNode* parent, std::vector<int>& placed) {
    char type;
    int value;
    if (!(std::cin >> type >> value)) throw std::invalid_argument("incomplete RA node");
    const int count = static_cast<int>(placed.size());
    if (type == 'L') {
        if (!parent || value < 0 || value >= count || placed[value]) {
            throw std::invalid_argument("invalid RA leaf");
        }
        const auto& predecessors = (*network)[value].getPrevs();
        FOR_BITSET(pred, predecessors) {
            if (!placed[pred]) throw std::invalid_argument("RA leaf precedes its producer");
        }
        placed[value] = 1;
        return new LTreeNode(static_cast<lid_t>(value), 1, parent);
    }
    if ((type != 'T' && type != 'S') || (!parent && type != 'T') || value < 1 || value > count) {
        throw std::invalid_argument("invalid RA cut");
    }
    auto node = new LTreeNode(Bitset{}, 1, parent, type == 'T' ? Type::T : Type::S);
    auto root = std::unique_ptr<LTreeNode>(parent ? nullptr : node);
    for (int index = 0; index < value; ++index) read_node(node, placed);
    if (root) return root.release();
    return node;
}

WholeSch read_seed(const Cluster& cluster) {
    std::vector<int> placed(network->len());
    auto tree = std::unique_ptr<LTreeNode>(read_node(nullptr, placed));
    for (auto seen : placed) if (!seen) throw std::invalid_argument("incomplete RA tree");
    tree->init_root();
    auto schedule = std::unique_ptr<SchNode>(SchNode::newNode(tree.get(), cluster, nullptr));
    if (!schedule->is_valid()) return {};
    tree->confirm();
    return {tree.release(), schedule.release()};
}
}

int main(int argc, char** argv) {
    try {
        if (argc != 6 && argc != 7) {
            throw std::invalid_argument("expected array_x array_y global_sram_bytes rounds seed [topology]");
        }
        const auto x = std::stoi(argv[1]), y = std::stoi(argv[2]);
        const auto capacity = std::stoull(argv[3]);
        const auto rounds = std::stoi(argv[4]);
        const auto seed = std::stoul(argv[5]);
        const auto topology = argc == 7 ? std::stoi(argv[6]) : 0;
        if (x < 1 || y < 1 || x > 255 || y > 255 || x*y*cores != 6144 || capacity < cores ||
            topology < 0 || topology > 2 || (rounds != 0 && rounds < 30)) {
            throw std::invalid_argument("invalid SET resource or search budget");
        }
        auto graph = read_graph();
        network = &graph;
        Cluster::xlen = topology == 0 ? 3 : 2;
        Cluster::ylen = topology == 0 ? 2 : 3;
        Cluster::stride = 1;
        Cluster::min_util = 0.75;
        const Cluster cluster(0, cores);
        const auto last_x = static_cast<mlen_t>(Cluster::xlen-1);
        const auto bottom = static_cast<mlen_t>(topology == 2 ? 1 : Cluster::ylen-1);
        NoC::dram_list = {{0, 0}, {0, bottom}, {last_x, 0}, {last_x, bottom}};
        NoC::DRAM_acc_cost = 7.5 * 8;
        NoC::hop_cost = 0.7 * 8;
        NoC::DRAM_bw = 6;
        NoC::NoC_bw = 24;
        ofm_ubuf_vol = 10 * 1024;
        const EyerissCore::Bus bus(0.018, 64);
        const EyerissCore::Buffers buffers{
            Core::Buffer(32, 0.0509*8, 256, 0.0506*8),
            Core::Buffer(128, 0.0545*8, 256, 0.054*8),
            Core::Buffer(1),
            Core::Buffer(capacity/cores, 0.1317125*8, 256, 0.234025*8),
        };
        const EyerissCore core(EyerissCore::PESetting(x, y, 0.018), 64, 0.0873, {bus, bus, bus}, buffers);
        EyerissMapper mapper(core);
        StdLayerEngine engine(&mapper);
        SchNode::layerMapper = &engine;
        SchNode::tot_batch = 1;
        network->set_utime(mapper);
        int seed_count;
        if (!(std::cin >> seed_count) || seed_count < 1 || seed_count > 4096) {
            throw std::invalid_argument("invalid seed count");
        }
        WholeSch schedule;
        int feasible_seeds = 0;
        for (int attempt = 0; attempt < seed_count; ++attempt) {
            auto candidate = read_seed(cluster);
            if (candidate) {
                ++feasible_seeds;
                schedule.min(candidate);
            }
        }
        if (!schedule) {
            std::cout << "RESULT {\"feasible\":false,\"evaluations\":" << seed_count << "}\n";
            return 0;
        }
        const auto initial_edp = schedule.sch->get_cost().cost();
        if (rounds) {
            SAEngine::nrounds = rounds;
            SAEngine search(seed);
            search.SA_search(schedule, cluster);
        }
        const auto cost = schedule.sch->get_cost();
        const auto& noc = schedule.sch->get_noc();
        access_t macs = 0;
        for (lid_t i = 0; i < graph.len(); ++i) {
            const auto& layer = graph[i].layer();
            if (REF_IS_INSTANCE(layer, ConvLayer)) macs += layer.get_num_op();
        }
        std::cout << std::setprecision(17) << "RESULT {\"feasible\":true,\"energy\":" << cost.energy
                  << ",\"cycles\":" << cost.time << ",\"edp\":" << cost.cost()
                  << ",\"initial_edp\":" << initial_edp << ",\"evaluations\":" << seed_count + rounds
                  << ",\"feasible_seeds\":" << feasible_seeds << ",\"mac_ops\":" << macs
                  << ",\"dram_accesses\":" << noc.get_tot_DRAM_acc()
                  << ",\"dram_energy\":" << noc.get_DRAM_cost() << ",\"noc_energy\":" << noc.get_hop_cost()
                  << ",\"noc_cycles\":" << noc.get_time()
                  << ",\"local_energy\":" << schedule.sch->get_ubuf_energy() + schedule.sch->get_buf_energy()
                                                + schedule.sch->get_bus_energy() + schedule.sch->get_mac_energy()
                  << ",\"cores\":" << cluster.num_cores() << ",\"macs_per_core\":" << core.mac_num
                  << ",\"topology\":" << topology << ",\"dram_ports\":" << NoC::dram_list.size()
                  << ",\"noc_links\":" << ((Cluster::xlen-1)*Cluster::ylen + (Cluster::ylen-1)*Cluster::xlen)
                  << ",\"sram_per_core\":" << core.ubuf().Size << ",\"tree\":";
        print_tree(*schedule.tree);
        std::cout << "}\n";
        schedule.del();
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
