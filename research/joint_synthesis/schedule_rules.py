"""Generate physical alternatives without accepting an architecture argument."""
from itertools import product
from .physical_plan import KernelPlan, Property, Schedule


def divisors(n):
    return tuple(i for i in range(1,n+1) if n%i==0)


def generate(graph):
    producer,consumer=graph.operators
    properties=tuple(Property(producer.output,l,s) for l,s in product(('row','col'),('sram','dram')))
    def schedules(op):
        return [Schedule(i,j,k,o) for i,j,k,o in product(divisors(op.left.rows),
            divisors(op.output.cols),divisors(op.left.cols),('ijk','ikj','jki'))]
    first=tuple(KernelPlan(producer,s,Property(producer.left,'row','dram'),p)
                for s,p in product(schedules(producer),properties))
    second=tuple(KernelPlan(consumer,s,p,Property(consumer.output,'row','dram'))
                 for s,p in product(schedules(consumer),properties))
    return first,second
